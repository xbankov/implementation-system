# -*- coding: utf-8 -*-

"""This module implements automatic detection and localization of projector screens on video using
semantic segmentation U-Net architecture implemented with FastAI library and post-processed into
ConvexQuadrangles

"""
import io
import logging
import os
from functools import partial
from logging import getLogger
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from fastai.metrics import dice
from fastai.vision import load_learner, defaults, SegmentationLabelList, open_mask, \
    SegmentationItemList, get_transforms, imagenet_stats, unet_learner, models

from video699.configuration import get_configuration
from video699.interface import (
    ScreenABC,
    ScreenDetectorABC
)
from video699.screen.semantic_segmentation.common import NotFittedException, acc, iou, get_label_from_image_name, \
    parse_methods, cv_image_to_tensor, tensor_to_cv_binary_image, resize_pred, get_top_left_x, create_labels, parse_lr

from video699.screen.semantic_segmentation.postprocessing import approximate
from video699.video.annotated import get_videos

logging.basicConfig(filename='example.log', level=logging.DEBUG)
LOGGER = getLogger(__name__)

ALL_VIDEOS = set(get_videos().values())
CONFIGURATION = get_configuration()['FastaiVideoScreenDetector']
VIDEOS_ROOT = Path(list(ALL_VIDEOS)[0].pathname).parents[2]
DEFAULT_VIDEO_PATH = VIDEOS_ROOT / 'video' / 'annotated'
DEFAULT_LABELS_PATH = VIDEOS_ROOT / 'screen' / 'labels'
DEFAULT_MODEL_PATH = VIDEOS_ROOT / 'screen' / 'models' / 'model'


class SegLabelListCustom(SegmentationLabelList):
    """
    Semantic segmentation custom label list that opens labels in binary mode. It is inherited from
    fastai class with RGB images.
    """

    def open(self, fn): return open_mask(fn, div=False, convert_mode='L')


class SegItemListCustom(SegmentationItemList):
    """
    Semantic segmentation custom item list with binary labels.

    """
    _label_cls = SegLabelListCustom


class FastAIScreenDetectorVideoScreen(ScreenABC):
    def __init__(self, frame, screen_index, coordinates):
        self._frame = frame
        self._screen_index = screen_index
        self._coordinates = coordinates

    @property
    def frame(self):
        return self._frame

    @property
    def coordinates(self):
        return self._coordinates


class FastAIScreenDetector(ScreenDetectorABC):
    def __init__(self, model_path=DEFAULT_MODEL_PATH, labels_path=DEFAULT_LABELS_PATH,
                 videos_path=DEFAULT_VIDEO_PATH, methods=None, train_params=None, filtered_by: Callable = None,
                 valid_func: Callable = None, device='cpu'):
        defaults.device = torch.device(device)
        self.model_path = model_path
        self.labels_path = labels_path
        self.videos_path = videos_path

        self.filtered_by = filtered_by
        self.valid_func = valid_func
        self.train_params = train_params
        self.methods = methods

        self.default_params()
        self.src_shape = np.array(
            [CONFIGURATION.getint('image_width'), CONFIGURATION.getint('image_height')])

        self.learner = None
        self.is_fitted = False

    def default_params(self):
        if not self.methods:
            self.methods = parse_methods(CONFIGURATION)

        if not self.filtered_by:
            self.filtered_by = lambda name: 'frame' in str(name)

        if not self.train_params:
            params = {}
            for param in ['batch_size', 'resize_factor', 'frozen_epochs', 'unfrozen_epochs', 'frozen_lr',
                          'unfrozen_lr']:
                params[param] = parse_lr(CONFIGURATION[param]) if '_lr' in param else CONFIGURATION.getint(param)
            self.train_params = params

    def train(self):
        create_labels(videos=ALL_VIDEOS, labels_path=self.labels_path)
        self.init_model()
        frozen_epochs = self.train_params['frozen_epochs']
        unfrozen_epochs = self.train_params['unfrozen_epochs']
        frozen_lr = self.train_params['frozen_lr']
        unfrozen_lr = self.train_params['unfrozen_lr']

        self.learner.fit_one_cycle(frozen_epochs, slice(frozen_lr))

        LOGGER.info("Unfreeze backbone part of the network.")
        self.learner.unfreeze()
        self.learner.fit_one_cycle(unfrozen_epochs, unfrozen_lr)

        self.is_fitted = True

    def detect(self, frame, methods=None):
        if not self.is_fitted:
            raise NotFittedException()

        pred = self.semantic_segmentation(frame)
        screens = self.post_processing(pred, frame, methods)
        return screens

    def semantic_segmentation(self, frame):
        tensor = cv_image_to_tensor(frame.image)
        tensor = self.learner.predict(tensor)
        pred = tensor_to_cv_binary_image(tensor)
        resized = resize_pred(pred, tuple(self.src_shape))
        return resized

    def post_processing(self, pred, frame, methods):
        if methods is None:
            methods = self.methods
        geos_quadrangles = approximate(pred, methods=methods)
        sorted_by_top_left_corner = sorted(geos_quadrangles, key=get_top_left_x)
        return [FastAIScreenDetectorVideoScreen(frame, screen_index, quadrangle) for
                screen_index, quadrangle in
                enumerate(sorted_by_top_left_corner)]

    def save(self, model_path: Path = None, chunk_size: int = 10000000):
        if not self.is_fitted:
            raise NotFittedException

        if not model_path:
            model_path = self.model_path

        if not model_path.parent.exists():
            os.mkdir(model_path.parent.absolute())

        with io.BytesIO() as stream:
            self.learner.export(stream)
            stream.seek(0)
            part_number = 1
            chunk = stream.read(chunk_size)
            while chunk:
                with open(str(model_path) + str(part_number) + '.mdl', mode='wb+') as chunk_file:
                    chunk_file.write(chunk)
                part_number += 1
                chunk = stream.read(chunk_size)

    def load(self, model_path: Path = None):
        if not model_path:
            model_path = self.model_path
        part_number = 1
        chunks = []
        while os.path.exists(str(model_path) + str(part_number) + '.mdl'):
            with open(str(model_path) + str(part_number) + '.mdl', mode='rb') as chunk_file:
                chunks.append(chunk_file.read())
            part_number += 1

        with io.BytesIO(b"".join(chunks)) as stream:
            self.learner = load_learner(path=model_path.parent, file=stream, bs=1)

        self.is_fitted = True

    def semantic_segmentation_batch(self, frames):
        pass

    def post_processing_batch(self, pred, methods):
        pass

    def detect_batch(self, frames):
        pass

    def init_model(self):
        size = self.src_shape // self.train_params['resize_factor']
        tfms = get_transforms(do_flip=True, flip_vert=True, max_rotate=10.0,
                              max_zoom=1.3, max_lighting=0.4, max_warp=1,
                              p_affine=0, p_lighting=0.75)

        get_label = partial(get_label_from_image_name, self.labels_path)

        if self.valid_func:
            src = (SegItemListCustom.from_folder(self.videos_path, ignore_empty=True, recurse=True)
                   .filter_by_func(self.filtered_by)
                   .split_by_valid_func(self.valid_func)
                   .label_from_func(get_label, classes=np.array(['non-screen', 'screen'])))

        else:
            src = (SegItemListCustom.from_folder(self.videos_path, ignore_empty=True, recurse=True)
                   .filter_by_func(self.filtered_by)
                   .split_none()
                   .label_from_func(get_label, classes=np.array(['non-screen', 'screen'])))

        LOGGER.info("Creating databunch with transformations")
        data = (src.transform(tfms, size=size, tfm_y=True)
                .databunch(bs=self.train_params['batch_size'])
                .normalize(imagenet_stats))

        LOGGER.info("Creating unet-learner with resnet18 backbone.")
        self.learner = unet_learner(data, models.resnet18, metrics=[acc, dice, iou])