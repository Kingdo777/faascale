### 1. Download the dataset
Download the dataset from the following link: [azurefunctions-dataset2019](https://azurecloudpublicdataset2.blob.core.windows.net/azurepublicdatasetv2/azurefunctions_dataset2019/azurefunctions-dataset2019.tar.xz)

### 2. Extract the dataset
Extract the dataset and copy one day's trace file to the `data` directory. such as:
- `data/app_memory_percentiles.anon.d01.csv`
- `data/function_durations_percentiles.anon.d01.csv`
- `data/invocations_per_function_md.anon.d01.csv`

### 3. Merge the dataset
Run the following command to merge the dataset:
```bash
python3 merge.py
```