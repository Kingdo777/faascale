// MIT License
//
// Copyright (c) 2022 Lixiang Ao
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

package daemon

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"log"
	"math/rand"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/ucsdsysnet/faasnap/models"
	"github.com/ucsdsysnet/faasnap/restapi/operations"

	"contrib.go.opencensus.io/exporter/prometheus"
	"go.opencensus.io/stats/view"
	"go.opencensus.io/trace"
)

type FaascaleMemConfig struct {
	StatsPollingIntervalS int  `json:"stats_polling_interval_s"`
	PreAllocMemory        bool `json:"pre_alloc_mem"`
	PreTdpFault           bool `json:"pre_tdp_fault"`
}

type Config struct {
	LogLevel          string            `json:"log_level"`
	BasePath          string            `json:"base_path"`
	Images            map[string]string `json:"images"`
	Kernels           map[string]string `json:"kernels"`
	Executables       map[string]string `json:"executables"`
	RedisHost         string            `json:"redis_host"`
	RedisPasswd       string            `json:"redis_passwd"`
	FaascaleMemConfig FaascaleMemConfig `json:"faascale_mem_config"`
}

type DaemonState struct {
	FnManager       *FunctionManager `json:"functionManager"`
	VmController    *VMController    `json:"vmController"`
	SnapshotManager *SnapshotManager `json:"snapshotManager"`
	Config          *Config          `json:"config"`
}

var fnManager *FunctionManager
var vmController *VMController
var ssManager *SnapshotManager

func registerPrometheus() *prometheus.Exporter {
	pe, err := prometheus.NewExporter(prometheus.Options{Namespace: "daemon"})
	if err != nil {
		log.Fatalf("Failed to create Prometheus exporter: %v", err)
	}
	view.RegisterExporter(pe)
	return pe
}

func Setup(s *http.Server, scheme, addr string) *DaemonState {

	var configFile = "/tmp/daemon.json"

	convertAbs := func(rel *string) {
		if !filepath.IsAbs(*rel) {
			abspath, err := filepath.Abs(*rel)
			if err != nil {
				log.Fatalf("Failed to convert path %v to absolute", *rel)
			}
			*rel = abspath
		}
	}

	convertAbs(&configFile)

	if _, err := os.Stat(configFile); os.IsNotExist(err) {
		log.Fatalf("config file %v not found", configFile)
	}
	bytes, err := ioutil.ReadFile(configFile)
	if err != nil {
		log.Fatalf("Failed to read config file at %v: %v", configFile, err)
	}
	var config Config
	json.Unmarshal(bytes, &config)

	verifyResource := func(rtype string, collection *map[string]string) {
		for alias, path := range *collection {
			if _, err := os.Stat(path); os.IsNotExist(err) {
				log.Fatalf("could not find %v %v at path %v when loading config", rtype, alias, path)
			}
			if !filepath.IsAbs(path) {
				log.Fatalf("all %v paths must be absolute: %v - %v", rtype, alias, path)
			}
		}
	}

	verifyResource("images", &config.Images)
	verifyResource("kernels", &config.Kernels)
	verifyResource("executables", &config.Executables)

	rand.Seed(time.Now().UnixNano())

	fnManager = NewFunctionManager(&config)
	vmController = NewVMController(&config)
	ssManager = NewSnapshotManager(&config)

	state := &DaemonState{
		FnManager:       fnManager,
		VmController:    vmController,
		SnapshotManager: ssManager,
	}

	return state
}

func CreateFunction(params operations.PostFunctionsParams) error {
	return fnManager.CreateFunction(*params.Function.FuncName, params.Function.Kernel, params.Function.Image, int(params.Function.Vcpu), int(params.Function.MemSize))
}

func StartVM(req *http.Request, name, ssId, namespace, kernel string, vcpu, mem int, enableBalloon, enableFaascale bool) (string, error) {
	if ssId == "" {
		return DoStartVM(req.Context(), name, namespace, kernel, vcpu, mem, enableBalloon, enableFaascale)
	} else {
		return "", nil // TODO
	}
}

func DoStartVM(ctx context.Context, function, namespace, kernel string, vcpu, mem int, enableBalloon, enableFaascale bool) (string, error) {
	_, span := trace.StartSpan(ctx, fmt.Sprintf("doStartVM_%v", function))
	defer span.End()
	if fn, ok := fnManager.Functions[function]; ok {
		if kernel == "" {
			kernel = fn.Kernel
		}
		if enableBalloon == false && enableFaascale == false {
			vcpu = fn.Vcpu
			mem = fn.MemSize
			kernel = fn.Kernel
		}
		if id, err := vmController.StartVM(&ctx, fn.Name, kernel, fn.Image, namespace, vcpu, mem, enableBalloon, enableFaascale); err != nil {
			return "", err
		} else {
			return id, nil
		}
	} else {
		log.Println("function", function, "not exist")
		return "", errors.New("function not exists")
	}
}

func StopVM(req *http.Request, vmID string) error {
	return vmController.StopVM(req, vmID)
}

func StartVMM(ctx context.Context, namespace string) (string, error) {
	_, span := trace.StartSpan(ctx, "start_vmm")
	defer span.End()
	return vmController.StartVMM(ctx, namespace)
}

func TakeSnapshot(req *http.Request, vmID string, snapshotType string, snapshotPath string, memFilePath string, version string, recordRegions bool, sizeThreshold, intervalThreshold int) (string, error) {
	vmController.Lock()
	vm, ok := vmController.Machines[vmID]
	vmController.Unlock()
	if !ok {
		log.Println("vmID not exists: ", vmID)
		return "", errors.New("vmID not exists")
	}
	if snapshotType == "" || snapshotPath == "" || memFilePath == "" || version == "" {
		return "", errors.New("snapshot configs incomplete")
	}

	ssId := "ss_" + RandStringRunes(8)
	snap := &Snapshot{
		SnapshotId:     ssId,
		Function:       vm.Function,
		SnapshotBase:   ssManager.config.BasePath + "/" + ssId,
		SnapshotType:   snapshotType,
		MemFilePath:    memFilePath,
		SnapshotPath:   snapshotPath,
		Version:        version,
		overlayRegions: map[int]int{},
		wsRegions:      [][]int{},
		loadOnce:       new(sync.Once),
	}

	var err error
	if err = vmController.TakeSnapshot(req, vmID, snap); err != nil {
		log.Println("snapshot failed: ", err)
		return "", err
	}

	if err := ssManager.RegisterSnapshot(snap); err != nil {
		return "", err
	}
	log.Println("snap.SnapshotId:", snap.SnapshotId)

	if recordRegions {
		if err = snap.RecordRegions(req.Context(), sizeThreshold, intervalThreshold); err != nil {
			log.Println("RecordRegions failed: ", err)
			return "", err
		}
	}

	return snap.SnapshotId, nil
}

func LoadSnapshot(req *http.Request, invoc *models.Invocation) (string, error) {
	snapshot, ok := ssManager.Snapshots[invoc.SsID]
	if !ok {
		log.Println("snapshot not exists")
		return "", errors.New("snapshot not exists")
	}
	vmID, err := vmController.LoadSnapshot(req, snapshot, invoc)
	if err != nil {
		log.Println("load snapshot failed")
		return "", err
	}

	return vmID, nil
}

func ChangeSnapshot(req *http.Request, ssID string, digHole, loadCache, dropCache bool) error {
	log.Println("ChangeSnapshot", ssID, digHole, loadCache, dropCache)
	snapshot, ok := ssManager.Snapshots[ssID]
	if !ok {
		log.Println("snapshot not exists")
		return errors.New("snapshot not exists")
	}
	return snapshot.UpdateCacheState(digHole, loadCache, dropCache)
}

func CopySnapshot(ctx context.Context, fromSnapshot, memFilePath string) (*models.Snapshot, error) {
	return ssManager.CopySnapshot(ctx, fromSnapshot, memFilePath)
}

func PutNetwork(req *http.Request, namespace, hostDevName, ifaceId, guestMac, guestAddr, uniqueAddr string) error {
	return vmController.AddNetwork(req, namespace, hostDevName, ifaceId, guestMac, guestAddr, uniqueAddr)
}

func InvokeFunction(req *http.Request, invoc *models.Invocation) (string, string, string, error) {
	var vmid string
	var snapshot *Snapshot
	var finished chan bool
	var scan bool
	span := trace.FromContext(req.Context())
	traceId := span.SpanContext().TraceID.String()

	switch {
	case invoc.VMID != "":
		// warm start
		var ok bool
		vmController.Lock()
		_, ok = vmController.Machines[invoc.VMID]
		vmController.Unlock()
		if !ok {
			log.Println("VM not exists")
			return "", "", traceId, errors.New("VM not exists")
		}
		vmid = invoc.VMID
	case invoc.SsID != "":
		// snapshot start
		var err error
		if vmid, err = LoadSnapshot(req, invoc); err != nil {
			log.Println("Snapshot start invocation failed")
			return "", "", traceId, err
		}
	default:
		// cold start
		var err error
		if vmid, err = DoStartVM(req.Context(), *invoc.FuncName, invoc.Namespace, "", 0, 0, false, false); err != nil {
			log.Println("Cold start invocation failed")
			return "", "", traceId, err
		}
		// wait for the VM to be ready
		_, err = vmController.WaitVMReady(req, vmid)
		if err != nil {
			log.Println("VM not ready")
			return "", "", traceId, err
		}
	}

	if invoc.SsID != "" && (*invoc.Mincore >= 0 || invoc.MincoreSize > 0) {
		if *invoc.Mincore >= 0 && invoc.MincoreSize > 0 {
			log.Println("both mincore modes specified")
			return "", "", traceId, errors.New("both mincore modes specified")
		}
		snapshot = ssManager.Snapshots[invoc.SsID]
		if snapshot.mincoreLayers == nil {
			scan = true
		}
	}

	if scan {
		finished = make(chan bool)
		go snapshot.ScanMincore(req, vmController.Machines[vmid].process.Pid, int(*invoc.Mincore), int(invoc.MincoreSize), finished)
		defer func() {
			go func() {
				finished <- true
			}()
		}()
	}

	resp, err := vmController.InvokeFunction(req, vmid, *invoc.FuncName, invoc.Params)
	if err != nil {
		return "", "", traceId, err
	}

	return resp, vmid, traceId, nil
}

func ChangeMincoreState(ctx context.Context, ssID string, fromRecordSize int, trimRegions bool, toWsFile string, inactiveWs, zeroWs bool, sizeThreshold, intervalThreshold int, nlayers []int64, dropWsCache bool) error {
	log.Println("ChangeMincoreState", nlayers, trimRegions)
	snapshot, ok := ssManager.Snapshots[ssID]
	if !ok {
		log.Println("snapshot", ssID, "not exists")
		return errors.New("snapshot not exists")
	}
	if fromRecordSize > 0 {
		if err := snapshot.EmulateMincore(ctx, fromRecordSize); err != nil {
			return err
		}
	}
	if trimRegions {
		if err := snapshot.TrimMincoreRegions(ctx); err != nil {
			return err
		}
	}
	if toWsFile != "" {
		if err := snapshot.createWsFile(ctx, toWsFile, inactiveWs, zeroWs, sizeThreshold, intervalThreshold); err != nil {
			return err
		}
	}
	if len(nlayers) > 0 {
		return snapshot.PreWarmMincore(ctx, nlayers)
	}
	if dropWsCache {
		if err := snapshot.dropWsCache(ctx); err != nil {
			return err
		}
	}
	return nil
}

func GetMincore(req *http.Request, ssID string) (*operations.GetSnapshotsSsIDMincoreOKBody, error) {
	return ssManager.GetMincore(req, ssID)
}

func CopyMincore(req *http.Request, ssID string, source string) error {
	return ssManager.CopyMincore(req, ssID, source)
}

func AddMincoreLayer(req *http.Request, ssID string, position int, fromDiff string) error {
	return ssManager.AddMincoreLayer(req, ssID, position, fromDiff)
}

// func getDmesg(w http.ResponseWriter, req *http.Request) {
// 	q := req.URL.Query()
// 	vmid := q.Get(vmID)
// 	vm, ok := vmController.Machines[vmid]
// 	if !ok {
// 		w.WriteHeader(500)
// 		w.Write([]byte(fmt.Sprintf("vm %v not found", vmid)))
// 		log.Println("vm ", vm, " not found")
// 		return
// 	}

// 	dmesg, err := vm.getDmesg(req.Context())
// 	if err != nil {
// 		w.WriteHeader(500)
// 		w.Write([]byte("Failed to get dmesg " + err.Error()))
// 		return
// 	}
// 	w.Write(dmesg)
// }
