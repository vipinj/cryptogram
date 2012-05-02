#!/usr/bin/env python

import base64
import sys
import logging
import os
from tempfile import NamedTemporaryFile
from json import JSONEncoder
from PIL import Image
from util import sha256hash
import cStringIO

class Encrypt(object):
  def __init__(self, image_buffer, codec, cipher):
    self.image_buffer = image_buffer
    self.codec = codec
    self.cipher = cipher
    self.temp_memory_file = image_buffer

  def _image_path_to_encrypted_data(self, image_path):
    logging.info('Reading raw image data.')
    with open(image_path, 'rb') as fh:
      raw_image_file_data = fh.read()
    return self._raw_image_data_to_encrypted_data(raw_image_file_data)

  def _raw_image_data_to_encrypted_data(self, raw_image_file_data):
    logging.info('Raw data: %s.' % raw_image_file_data[:10])
    base64_image_file_data = base64.b64encode(raw_image_file_data)

    logging.info('Cipher encoding data.')
    encrypted_data = self.cipher.encode(base64_image_file_data)

    # Compute integrity check on the encrypted data, which should be base64
    # (in the case of V8Cipher, this includes the jsonified data).
    if self.cipher.__class__.__name__ == 'V8Cipher':
      _to_hash = \
          encrypted_data['iv'] + \
          encrypted_data['salt'] + \
          encrypted_data['ct']
      logging.info('Integrity hash input: %s.' % _to_hash[:32])
      integrity_check_value = sha256hash(_to_hash)
      logging.info('Integrity hash value: %s.' % integrity_check_value)
    else:
      integrity_check_value = sha256hash(encrypted_data)

    # For V8Cipher, we have to tease apart the JSON in order to set the
    # encrypted_data string correctly.
    if self.cipher.__class__.__name__ == 'V8Cipher':
      encrypted_data = \
          integrity_check_value + \
          encrypted_data['iv'] + \
          encrypted_data['salt'] + \
          encrypted_data['ct']

    logging.info('Returning encrypted data.')
    return encrypted_data

  def _reduce_image_quality(self, image_path):
    logging.info('Requalitying image.')
    image_path.seek(0)
    im = Image.open(image_path)

    new_file = cStringIO.StringIO()
    im.save(new_file, 'jpeg', quality=77)
    logging.info('Deleting image.')
    del im
    return new_file


  def _reduce_image_size(self, image_path, scale):
    logging.info('Resizing image.')

    logging.info('Opening image')
    image_path.seek(0)
    im = Image.open(image_path)

    logging.info('Opened. Resizing')
    width, height = im.size
    im = im.resize((int(width * scale), int(height * scale)))

    new_file = cStringIO.StringIO()
    im.save(new_file, 'jpeg', quality=77)
    del im
    return new_file


  def upload_encrypt(self, dimension_limit = 2048):
    requality_limit = 1
    requality_count = 0
    rescale_count = 0

    prospective_image_dimensions = self.codec.get_prospective_image_dimensions

    _image_buffer = self.temp_memory_file

    while True:
      logging.info('Start of while loop.')

      _image_buffer.seek(0)
      _ = Image.open(_image_buffer)
      _w, _h = _.size
      logging.info('Cleartext image dimensions: (%d, %d).' % (_w, _h))
      del _

      encrypted_data = self._raw_image_data_to_encrypted_data(
        _image_buffer.getvalue())

      width, height = prospective_image_dimensions(encrypted_data)
      if width <= dimension_limit and height <= dimension_limit:
        break

      del encrypted_data
      logging.info('Dimensions too large (w: %d, h: %d).' % (width, height))

      # Strategies to reduce raw bytes that we need to encrypt: requality,
      # rescale.
      if requality_count < requality_limit:
        logging.info('Requality image.')
        _ = self._reduce_image_quality(_image_buffer)
        del _image_buffer
        _image_buffer = _
        requality_count += 1

      else:
        rescale_count += 1
        logging.info('Rescale with original image.')
        _ = self._reduce_image_size(
          self.image_buffer, 1.0 - (0.05 * rescale_count))
        del _image_buffer
        _image_buffer = _

    del _image_buffer
    return encrypted_data

  def encrypt(self):
    image = Image.open(self.image_path)
    with open(self.image_path, 'rb') as fh:
      raw_image_file_data = fh.read()
    base64_image_file_data = base64.b64encode(raw_image_file_data)
    encrypted_data = cipher.encode(base64_image_file_data)
    width, length = self.codec.get_prospective_image_dimensions()
