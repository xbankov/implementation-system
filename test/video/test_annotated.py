# -*- coding: utf-8 -*-

import unittest

import cv2 as cv
from dateutil.parser import parse as datetime_parse
from video699.video.annotated import get_videos


VIDEOS = get_videos()
VIDEO_URI = 'https://is.muni.cz/auth/el/{faculty}/{term}/{course}/um/vi/?videomuni={fname}'.format(
    course='PB029',
    faculty=1433,
    fname='PB029-D3-20161026.mp4',
    term='podzim2016',
)
VIDEO_DIRNAME = 'PB029-D3-20161026.mp4'
VIDEO_NUM_FRAMES = 90378
VIDEO_FPS = 15
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 576
VIDEO_DATETIME = datetime_parse('2016-10-26T00:00:00+00:00')
VIDEO_NUM_DOCUMENTS = 4
VIDEO_FRAME_NUMBERS = (
    2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000, 18000, 20000, 24000, 30000, 40000, 60000,
    62000, 64000, 66000, 68000, 78000, 80000, 82000, 84000, 86000, 88000, 90000,
)
VGG256_SHAPE = (256,)
FIRST_DOCUMENT_FILENAME = 'slides01.pdf'
SECOND_DOCUMENT_FILENAME = 'slides02.pdf'
FIRST_DOCUMENT_NUM_PAGES = 32
SECOND_DOCUMENT_NUM_PAGES = 10


class TestAnnotatedSampledVideo(unittest.TestCase):
    """Tests the ability of the AnnotatedSampledVideo class to read human annotations.

    """

    def setUp(self):
        self.video = VIDEOS[VIDEO_URI]

    def test_video_properties(self):
        self.assertEqual(VIDEO_DIRNAME, self.video.dirname)
        self.assertEqual(VIDEO_NUM_FRAMES, self.video.num_frames)
        self.assertEqual(VIDEO_FPS, self.video.fps)
        self.assertEqual(VIDEO_WIDTH, self.video.width)
        self.assertEqual(VIDEO_HEIGHT, self.video.height)
        self.assertEqual(VIDEO_DATETIME, self.video.datetime)

    def test_video_contains_n_documents(self):
        self.assertEqual(VIDEO_NUM_DOCUMENTS, len(self.video.documents))

    def test_video_produces_n_frames(self):
        self.assertEqual(len(VIDEO_FRAME_NUMBERS), len(list(iter(self.video))))


class TestAnnotatedSampledVideoFrame(unittest.TestCase):
    """Tests the ability of the AnnotatedSampledVideoFrame class to read human annotations.

    """

    def setUp(self):
        video = VIDEOS[VIDEO_URI]
        frame_iterator = iter(video)
        self.first_frame = next(frame_iterator)
        self.second_frame = next(frame_iterator)

    def test_frame_numbers(self):
        self.assertTrue(VIDEO_FRAME_NUMBERS[0], self.first_frame.number)
        self.assertTrue(VIDEO_FRAME_NUMBERS[1], self.second_frame.number)

    def test_frame_image(self):
        frame_image = self.first_frame.image
        height, width, _ = frame_image.shape
        self.assertEqual(VIDEO_WIDTH, width)
        self.assertEqual(VIDEO_HEIGHT, height)

        blue, green, red = cv.split(frame_image)
        self.assertTrue(red[90, 490] > blue[90, 490] and red[90, 490] > green[90, 490])
        self.assertTrue(green[190, 340] > red[190, 340] and green[190, 340] > blue[190, 340])
        self.assertTrue(blue[50, 320] > red[50, 320] and blue[50, 320] > green[50, 320])

    def test_vgg256_dimensions(self):
        self.assertEqual(VGG256_SHAPE, self.first_frame.vgg256.imagenet.shape)
        self.assertEqual(VGG256_SHAPE, self.first_frame.vgg256.imagenet_and_places2.shape)
        self.assertEqual(VGG256_SHAPE, self.second_frame.vgg256.imagenet.shape)
        self.assertEqual(VGG256_SHAPE, self.second_frame.vgg256.imagenet_and_places2.shape)


class TestAnnotatedSampledVideoDocument(unittest.TestCase):
    """Tests the ability of the AnnotatedSampledVideoDocument class to read human annotations.

    """

    def setUp(self):
        video = VIDEOS[VIDEO_URI]
        self.first_document = video.documents[FIRST_DOCUMENT_FILENAME]
        self.second_document = video.documents[SECOND_DOCUMENT_FILENAME]

    def test_reads_n_pages(self):
        self.assertEqual(FIRST_DOCUMENT_NUM_PAGES, len(list(self.first_document)))
        self.assertEqual(SECOND_DOCUMENT_NUM_PAGES, len(list(self.second_document)))
