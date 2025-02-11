#!/usr/bin/env python3
# -*- coding:utf-8 -*-

# Copyright 2019 Xilinx Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and 
# limitations under the License.

# Code are based on
# https://github.com/fmassa/vision/blob/voc_dataset/torchvision/datasets/voc.py
# Copyright (c) Francisco Massa.
# Copyright (c) Ellis Brown, Max deGroot.
# Copyright (c) Megvii, Inc. and its affiliates.

import os
import os.path
import pickle
from loguru import logger
from tqdm import tqdm

import cv2
import numpy as np

from yolox.evaluators.voc_eval import voc_eval

from .datasets_wrapper import Dataset
from ..dataloading import get_yolox_datadir

from .kitti_common import get_label_annos
from .kitti_eval import get_official_eval_result


class KITTIDetection(Dataset):

    """
    KITTI Detection Dataset Object

    input is image, target is annotation

    Args:
        root (string): filepath to VOCdevkit folder.
        image_set (string): imageset to use (eg. 'train', 'val', 'test')
        transform (callable, optional): transformation to perform on the
            input image
        dataset_name (string, optional): which dataset to load
    """

    def __init__(
        self,
        data_dir,
        image_set="train.txt",
        img_size=(384, 1248),
        preproc=None,
        dataset_name="kitti",
        cache=False,
    ):
        super().__init__(img_size)
        if data_dir is None:
            # data_dir = os.path.join(get_yolox_datadir(), "KITTI")
            data_dir = os.path.join('data', "KITTI")
        assert image_set in ["train.txt", "val.txt"], "Image_set of KITTI should be 'train' or 'val'!"
        # self._year = '2017'
        self.root = data_dir
        self.image_set = image_set
        self.img_size = img_size
        self.preproc = preproc
        self.name = dataset_name
        self._annopath = os.path.join(self.root, "training", "label_2", "%s.txt")
        self._imgpath = os.path.join(self.root, "training", "image_2", "%s.png")
        self.label_dir = os.path.join(self.root, "training", "label_2")

        # self.classes = ('Car', 'Pedestrian', 'Cyclist')
        self.classes = ('Car',)
        self.class2id = dict(zip(self.classes, range(len(self.classes))))
        self.ids = list()
        split_path = os.path.join(self.root, "ImageSets", image_set)
        for line in open(split_path):
            self.ids.append(line.strip())

        self.img_infos = self._record_img_shapes()
        self.annotations = self._load_coco_annotations()
        self.imgs = None
        if cache:
            self._cache_images()

    def __len__(self):
        return len(self.ids)

    def _record_img_shapes(self):
        print("Collecting image shape info...")
        img_infos = list()
        for index in tqdm(range(len(self.ids))):
            img = self.load_image(index)
            img_infos.append(tuple(img.shape[:2]))
        return img_infos

    def _load_coco_annotations(self):
        return [self.load_anno_from_ids(_ids) for _ids in range(len(self.ids))]

    def eval(self, results_dir='predictions'):
        logger.info("==> Loading detections and GTs...")
        img_ids = [int(id) for id in self.ids]
        dt_annos = get_label_annos(results_dir)
        gt_annos = get_label_annos(self.label_dir, img_ids)

        # test_id = {'Car': 0, 'Pedestrian':1, 'Cyclist': 2}
        test_id = {'Car': 0}

        results_str = ''
        results_dict = {}
        for category in self.classes:
            cls_str, cls_dict = get_official_eval_result(gt_annos, dt_annos, test_id[category])
            results_str += cls_str
            results_dict.update(cls_dict)
        return results_str, results_dict

    def _cache_images(self):
        logger.warning(
            "\n********************************************************************************\n"
            "You are using cached images in RAM to accelerate training.\n"
            "This requires large system RAM.\n"
            "Make sure you have 60G+ RAM and 19G available disk space for training VOC.\n"
            "********************************************************************************\n"
        )
        max_h = self.img_size[0]
        max_w = self.img_size[1]
        cache_file = self.root + "/img_resized_cache_" + self.name + ".array"
        if not os.path.exists(cache_file):
            logger.info(
                "Caching images for the first time. This might take about 3 minutes for VOC"
            )
            self.imgs = np.memmap(
                cache_file,
                shape=(len(self.ids), max_h, max_w, 3),
                dtype=np.uint8,
                mode="w+",
            )
            from multiprocessing.pool import ThreadPool

            NUM_THREADs = min(8, os.cpu_count())
            loaded_images = ThreadPool(NUM_THREADs).imap(
                lambda x: self.load_resized_img(x),
                range(len(self.annotations)),
            )
            pbar = tqdm(enumerate(loaded_images), total=len(self.annotations))
            for k, out in pbar:
                self.imgs[k][: out.shape[0], : out.shape[1], :] = out.copy()
            self.imgs.flush()
            pbar.close()
        else:
            logger.warning(
                "You are using cached imgs! Make sure your dataset is not changed!!\n"
                "Everytime the self.input_size is changed in your exp file, you need to delete\n"
                "the cached data and re-generate them.\n"
            )

        logger.info("Loading cached imgs...")
        self.imgs = np.memmap(
            cache_file,
            shape=(len(self.ids), max_h, max_w, 3),
            dtype=np.uint8,
            mode="r+",
        )

    def load_anno_from_ids(self, index):
        img_id = self.ids[index]
        lab_path = self._annopath % img_id
        res = np.empty((0,5)) # xmin, ymin, xmax, ymax, cls_id
        with open(lab_path, 'r') as fr:
            lines = fr.readlines()
        for line in lines:
            line = line.strip().split(' ')
            if line[0] not in self.classes:
                continue
            cls_id = self.class2id[line[0]]
            xmin, ymin, xmax, ymax = [int(float(coor)) for coor in line[4:8]]
            res = np.vstack((res, [xmin, ymin, xmax, ymax, cls_id]))
        height, width = self.img_infos[index]

        r = min(self.img_size[0] / height, self.img_size[1] / width)
        res[:, :4] *= r
        resized_info = (int(height * r), int(width * r))

        return (res, resized_info)

    def load_anno(self, index):
        return self.annotations[index][0]

    def load_resized_img(self, index):
        img = self.load_image(index)
        r = min(self.img_size[0] / img.shape[0], self.img_size[1] / img.shape[1])
        resized_img = cv2.resize(
            img,
            (int(img.shape[1] * r), int(img.shape[0] * r)),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.uint8)

        return resized_img

    def load_image(self, index):
        img_id = self.ids[index]
        img = cv2.imread(self._imgpath % img_id, cv2.IMREAD_COLOR)
        assert img is not None

        return img

    def pull_item(self, index):
        """Returns the original image and target at an index for mixup

        Note: not using self.__getitem__(), as any transformations passed in
        could mess up this functionality.

        Argument:
            index (int): index of img to show
        Return:
            img, target
        """
        if self.imgs is not None:
            target, resized_info = self.annotations[index]
            pad_img = self.imgs[index]
            img = pad_img[: resized_info[0], : resized_info[1], :].copy()
        else:
            img = self.load_resized_img(index)
            target, _ = self.annotations[index]

        img_info = self.img_infos[index]

        return img, target, img_info, index

    @Dataset.mosaic_getitem
    def __getitem__(self, index):
        img, target, img_info, img_id = self.pull_item(index)

        if self.preproc is not None:
            img, target = self.preproc(img, target, self.input_dim)

        return img, target, img_info, img_id

    def evaluate_detections(self, all_boxes, output_dir=None):
        """
        all_boxes is a list of length number-of-classes.
        Each list element is a list of length number-of-images.
        Each of those list elements is either an empty list []
        or a numpy array of detection.

        all_boxes[class][image] = [] or np.array of shape #dets x 5
        """
        self._write_voc_results_file(all_boxes)
        IouTh = np.linspace(
            0.5, 0.95, int(np.round((0.95 - 0.5) / 0.05)) + 1, endpoint=True
        )
        mAPs = []
        for iou in IouTh:
            mAP = self._do_python_eval(output_dir, iou)
            mAPs.append(mAP)

        print("--------------------------------------------------------------")
        print("map_5095:", np.mean(mAPs))
        print("map_50:", mAPs[0])
        print("--------------------------------------------------------------")
        return np.mean(mAPs), mAPs[0]

    def _get_voc_results_file_template(self):
        filename = "comp4_det_test" + "_{:s}.txt"
        filedir = os.path.join(self.root, "results", "VOC" + self._year, "Main")
        if not os.path.exists(filedir):
            os.makedirs(filedir)
        path = os.path.join(filedir, filename)
        return path

    def _write_voc_results_file(self, all_boxes):
        for cls_ind, cls in enumerate(self.classes):
            cls_ind = cls_ind
            if cls == "__background__":
                continue
            print("Writing {} KITTI results file".format(cls))
            filename = self._get_voc_results_file_template().format(cls)
            with open(filename, "wt") as f:
                for im_ind, index in enumerate(self.ids):
                    index = index[1]
                    dets = all_boxes[cls_ind][im_ind]
                    if dets == []:
                        continue
                    for k in range(dets.shape[0]):
                        f.write(
                            "{:s} {:.3f} {:.1f} {:.1f} {:.1f} {:.1f}\n".format(
                                index,
                                dets[k, -1],
                                dets[k, 0] + 1,
                                dets[k, 1] + 1,
                                dets[k, 2] + 1,
                                dets[k, 3] + 1,
                            )
                        )

    def _do_python_eval(self, output_dir="output", iou=0.5):

        name = self.image_set
        annopath = os.path.join(self.root, "training", "label_2", "{:s}.txt")
        imagesetfile = os.path.join(self.root, "ImageSets", name)
        cachedir = os.path.join(self.root, "annotations_cache", "VOC" + self._year, name)
        
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        aps = []

        # The PASCAL VOC metric changed in 2010
        # TODO:
        use_07_metric = True if int(self._year) < 2010 else False

        print("Eval IoU : {:.2f}".format(iou))
        if output_dir is not None and not os.path.isdir(output_dir):
            os.mkdir(output_dir)
        for i, cls in enumerate(self.classes):

            if cls == "__background__":
                continue

            filename = self._get_voc_results_file_template().format(cls)
            rec, prec, ap = voc_eval(
                filename,
                annopath,
                imagesetfile,
                cls,
                cachedir,
                ovthresh=iou,
                use_07_metric=use_07_metric,
            )
            aps += [ap]
            if iou == 0.5:
                print("AP for {} = {:.4f}".format(cls, ap))
            if output_dir is not None:
                with open(os.path.join(output_dir, cls + "_pr.pkl"), "wb") as f:
                    pickle.dump({"rec": rec, "prec": prec, "ap": ap}, f)
        if iou == 0.5:
            print("Mean AP = {:.4f}".format(np.mean(aps)))
            print("~~~~~~~~")
            print("Results:")
            for ap in aps:
                print("{:.3f}".format(ap))
            print("{:.3f}".format(np.mean(aps)))
            print("~~~~~~~~")
            print("")
            print("--------------------------------------------------------------")
            print("Results computed with the **unofficial** Python eval code.")
            print("Results should be very close to the official MATLAB eval code.")
            print("Recompute with `./tools/reval.py --matlab ...` for your paper.")
            print("-- Thanks, The Management")
            print("--------------------------------------------------------------")

        return np.mean(aps)
