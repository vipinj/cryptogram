#!/usr/bin/env python

from Crypto.Cipher import AES
from PIL import Image, ImageDraw
from tempfile import NamedTemporaryFile
import PIL
import base64
import binascii
import gflags
import logging
import math
import os
import sys
import threading

logging.basicConfig(filename='code.log', level=logging.INFO)

FLAGS = gflags.FLAGS
gflags.DEFINE_multistring('image', None, 'image to encode and encrypt',
                          short_name = 'i')

class Cipher(object):
  # the block size for the cipher object; must be 16, 24, or 32 for AES
  BLOCK_SIZE = 32

  # the character used for padding--with a block cipher such as AES, the value
  # you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
  # used to ensure that your value is always a multiple of BLOCK_SIZE
  PADDING = '{'

  def __init__(self, password):
    secret = self._pad(password)
    self.cipher = AES.new(secret)

  def _pad(self, s):
    return s + (self.BLOCK_SIZE - len(s) % self.BLOCK_SIZE) * self.PADDING

  def encode(self, message):
    return base64.b64encode(self.cipher.encrypt(self._pad(message)))

  def decode(self, encoded):
    return self.cipher.decrypt(base64.b64decode(encoded)).rstrip(self.PADDING)


class SeeMeNotImage(threading.Thread):
  image = None
  b64_image = None
  rgb_image = None

  def __init__(self, image_path, scale, quality=None, block_size=None):
    self.image_path = image_path
    self.scale = scale
    self.quality = quality
    self.block_size = block_size
    threading.Thread.__init__(self)

  def _get_wrgbk(self, block):
    upper_thresh = 150
    lower_thresh = 50
    count = 0
    rt = 0.0
    gt = 0.0
    bt = 0.0

    # logging.debug(str(list(block.getdata())))
    block_len = len(list(block.getdata()))
    for i in range(0, block_len, 4):
      rt += list(block.getdata())[i][0]
      gt += list(block.getdata())[i][1]
      bt += list(block.getdata())[i][2]
      count += 1
    r = rt / count
    g = gt / count
    b = bt / count

    # logging.debug('%(r)f %(g)f %(b)f' % locals())
    if (r > upper_thresh and b > upper_thresh and g > upper_thresh): return 0
    if (r < lower_thresh and g < lower_thresh and b < lower_thresh): return 4

    if ( r > g and r > b): return 1
    if ( g > r and g > b): return 2
    if ( b > r and b > g): return 3

    return -1


  def rescale(self):
    width, height = self.image.size
    self.image = self.image.resize(
      (int(width * self.scale), int(height * self.scale)))

  def requality(self, quality):
    with NamedTemporaryFile() as fh:
      self.image_path = fh.name + '.jpg'
      self.image.save(self.image_path, quality=quality)
      self.image = Image.open(self.image_path)

  def encode(self):
    with NamedTemporaryFile() as fh:
      image_path = fh.name + '.jpg'
      self.image.save(image_path)
    with open(image_path, 'rb') as fh:
      initial_data = fh.read()

    self.bin_image = initial_data

  def encrypt(self, password):
    c = Cipher(password)
    # with open(self.image_path,'rb') as fh:
    #   self.b64encrypted = c.encode(base64.b64encode(fh.read()))
    self.b64encrypted = c.encode(base64.b64encode(self.bin_image))
    logging.debug('Encrypted b64: ' + self.b64encrypted)

    hex_data = binascii.hexlify(self.b64encrypted)
    logging.debug('Original encrypted hex Data: ' + hex_data)

    num_data = len(hex_data)
    width, length = self.image.size

    width_power_2 = int(math.log(width, 2))
    TARGET_WIDTH = 2 ** width_power_2
    logging.info('Width: %d.' % TARGET_WIDTH)

    width = int(TARGET_WIDTH / (self.block_size * 2));
    height = int(math.ceil(num_data / width))
    logging.info('Encrypted image (w x h): (%d x %d).' % (width, height))
    logging.info('Expected image (w x h): (%d x %d).' % \
                    (TARGET_WIDTH, height*self.block_size))
    self.rgb_image = Image.new('RGB', (width * self.block_size * 2,
                                       height * self.block_size))

    colors = [(255,255,255), (255,0,0), (0,255,0), (0,0,255)]
    logging.info('Len of hex_data: %d' % num_data)
    self.coords = []

    for i, hex_datum in enumerate(hex_data):
      hex_val = int(hex_datum, 16)
      base4_1 = int(hex_val / 4.0) # Implicit floor.
      base4_0 = int(hex_val - (base4_1 * 4))
      y_coord = int(i / width)
      x_coord = int(i - (y_coord * width))
      draw = ImageDraw.Draw(self.rgb_image)

      # base4_0
      base4_0_x = int(x_coord * self.block_size * 2)
      base4_0_y = int(y_coord * self.block_size)
      self.coords.append((base4_0_x, base4_0_y))
      draw.rectangle([(base4_0_x, base4_0_y),
                      (base4_0_x + self.block_size, base4_0_y + self.block_size)],
                     fill=colors[base4_0])

      # base4_1
      base4_1_x = int((x_coord * self.block_size * 2) + self.block_size)
      base4_1_y = int(y_coord * self.block_size)
      self.coords.append((base4_1_x, base4_1_y))
      draw.rectangle([(base4_1_x, base4_1_y),
                      (base4_1_x + self.block_size, base4_1_y + self.block_size)],
                     fill=colors[base4_1])

    filename = 'rgb.jpg'
    self.rgb_image.save(filename, quality=100)
    return filename

  def extract_rgb(self):
    self.rgb_image = Image.open('rgb.jpg')
    width, height = self.rgb_image.size
    im = Image.new('RGB', (width,height))
    hex_string = ''
    count = 0
    self.extracted_coords = []
    # self.rgb_image.show()
    for y in range(0, height, self.block_size):
      for x in range(0, width, self.block_size * 2):

        block0 = self.rgb_image.crop(
          (x, y, x + self.block_size, y + self.block_size))
        block1 = self.rgb_image.crop(
          (x + self.block_size, y, x + (2 * self.block_size), y + self.block_size))

        block0.load()
        block1.load()
        hex0 = self._get_wrgbk(block0)
        hex1 = self._get_wrgbk(block1)

        self.extracted_coords.append((x, y))
        self.extracted_coords.append((x + self.block_size, y))

        # Found black, stop.
        if (hex0 == 4 or hex1 == 4):
          logging.info('Done at (%d, %d).' % (x, y))
          break

        hex_num = hex0 + hex1 * 4
        hex_value = hex(hex_num).replace('0x','')
        hex_string += hex_value
        count += 1

    coord_diff = [coord for coord in
                  [orig for orig in self.coords
                   if orig not in self.extracted_coords]]

    logging.debug('Coord diff: %s.' % str(coord_diff))
    logging.info('Extracted count: %d.' % count)
    logging.debug('Extracted hex_string: %s' % hex_string)
    errors = 0

    self.extracted_encrypted_base64 = binascii.unhexlify(hex_string)
    logging.debug('Extracted encrypted b64: ' + self.extracted_encrypted_base64)

    original = self.b64encrypted
    print len(original)
    print len(self.extracted_encrypted_base64)

  def decrypt(self, password):
    c = Cipher(password)
    decrypted = c.decode(self.extracted_encrypted_base64)
    to_write = base64.b64decode(decrypted)
    with open('decrypted.jpg', 'wb') as fh:
      fh.write(to_write)


  def run(self):
    # Open the image.
    self.image = Image.open(self.image_path)

    # Re{scale,quality} image.
    self.rescale()
    self.requality(self.quality)

    self.encode()
    filename = self.encrypt('helloworld')

    self.extract_rgb()
    self.decrypt('helloworld')


def main(argv):
  try:
    argv = FLAGS(argv)  # parse flags
  except gflags.FlagsError, e:
    print '%s\\nUsage: %s ARGS\\n%s' % (e, sys.argv[0], FLAGS)
    sys.exit(1)

  c = Cipher('this is my password')
  encoded = c.encode('this is my secret message')
  print encoded

  c1 = Cipher('this is my password')
  decoded = c1.decode(encoded)
  print decoded

  smni = SeeMeNotImage('maple-small.jpg', 0.2, 100, 2)
  smni.start()

if __name__ == '__main__':
  main(sys.argv)
