import uuid
from time import time

import redis
from PIL import Image, ImageFilter

TMP = '/dev/shm/'

def flip(image, file_name):
    path_list = []
    path = TMP + "flip-left-right-" + file_name
    img = image.transpose(Image.FLIP_LEFT_RIGHT)
    img.save(path)
    path_list.append(path)

    path = TMP + "flip-top-bottom-" + file_name
    img = image.transpose(Image.FLIP_TOP_BOTTOM)
    img.save(path)
    path_list.append(path)

    return path_list


def rotate(image, file_name):
    path_list = []
    path = TMP + "rotate-90-" + file_name
    img = image.transpose(Image.ROTATE_90)
    img.save(path)
    path_list.append(path)

    path = TMP + "rotate-180-" + file_name
    img = image.transpose(Image.ROTATE_180)
    img.save(path)
    path_list.append(path)

    path = TMP + "rotate-270-" + file_name
    img = image.transpose(Image.ROTATE_270)
    img.save(path)
    path_list.append(path)

    return path_list


def imgfilter(image, file_name):
    path_list = []
    path = TMP + "blur-" + file_name
    img = image.filter(ImageFilter.BLUR)
    img.save(path)
    path_list.append(path)

    path = TMP + "contour-" + file_name
    img = image.filter(ImageFilter.CONTOUR)
    img.save(path)
    path_list.append(path)

    path = TMP + "sharpen-" + file_name
    img = image.filter(ImageFilter.SHARPEN)
    img.save(path)
    path_list.append(path)

    return path_list


def gray_scale(image, file_name):
    path = TMP + "gray-scale-" + file_name
    img = image.convert('L')
    img.save(path)
    return [path]


def resize(image, file_name):
    path = TMP + "resized-" + file_name
    image.thumbnail((128, 128))
    image.save(path)
    return [path]

def image_processing(file_name, image_path):
    path_list = []
    start = time()
    with Image.open(image_path) as image:
        tmp = image
        # path_list += flip(image, file_name)
        path_list += rotate(image, file_name)
        # path_list += imgfilter(image, file_name)
        # path_list += gray_scale(image, file_name)
        # path_list += resize(image, file_name)

    latency = time() - start
    return latency, path_list


def lambda_handler(event, context):
    in_key = event['input_object_key']
    out_key_prefix = event['output_object_key_prefix']
    r = context['r']

    download_path = TMP + in_key
    with open(download_path, 'wb') as f:
        f.write(r.get(in_key))
    ts1 = time()
    latency, path_list = image_processing(in_key, download_path)
    ts2 = time()
    for upload_path in path_list:
        with open(upload_path, 'rb') as f:
            r.set(out_key_prefix+upload_path.split("/")[-1], f.read())

    return [ts1, ts2]


if __name__ == '__main__':
    event = {
        "input_object_key": "pexels-photo-2051572.jpeg",
        "output_object_key_prefix": "outputimg-"
    }
    print(lambda_handler(event, {'r': redis.Redis(host="222.20.94.67", port=6379, db=0, password="")}))
