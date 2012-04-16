#!/usr/bin/en python
import logging
from NewImageDimensions import NewImageDimensions
from PIL import Image

class Codec(object):
  def __init__(self, symbol_shape, original_hw_ratio, encoding_shape_translator,
               symbol_fill_translator):
    self.symbol_shape = symbol_shape
    self.original_hw_ratio = original_hw_ratio
    self.encoding_shape_translator = encoding_shape_translator
    self.symbol_fill_translator = symbol_fill_translator

  def encode(self, data):
    data_len = len(data)
    self.new_image_dimensions = NewImageDimensions(
      self.original_hw_ratio, data_len, self.symbol_shape)

    new_image_width, new_image_height = \
        self.new_image_dimensions.get_image_dimensions()
    new_image_symbol_width, new_image_symbol_height = \
        self.new_image_dimensions.get_image_symbol_dimensions()

    new_image = Image.new('RGB', (new_image_width, new_image_height))
    logging.info('Image dimensions: width (%d) height (%d).' % \
                   (new_image_width, new_image_height))
    pixel = new_image.load()
    shape_width, shape_height = self.symbol_shape.get_shape_size()
    for i, datum in enumerate(data):
      y_coord = int(i / float(new_image_symbol_width))
      x_coord = int(i - (y_coord * new_image_symbol_width))
      symbol_values = self.encoding_shape_translator.encoding_to_shapes(datum)
      assert (len(symbol_values) == self.symbol_shape.get_num_symbol_shapes())

      base_x = x_coord * shape_width
      base_y = y_coord * shape_height

      for sym_i, symbol_val in enumerate(symbol_values):
        fill = self.symbol_fill_translator.symbol_to_fill(symbol_val)
        coords = self.symbol_shape.get_symbol_shape_coords(sym_i + 1)
        for x,y in coords:
          pixel[base_x + x, base_y + y] = (fill, fill, fill)
    return new_image

  def decode(self, read_image):
    width, height = read_image.size
    image = read_image.convert('RGB') # Ensure format is correct.

    shape_width, shape_height = self.symbol_shape.get_shape_size()
    pixels = image.load()
    extracted_data = ''
    for y_coord in range(0, height, shape_height):
      for x_coord in range(0, width, shape_width):
        values = {}
        for symbol_val in range(self.symbol_shape.get_num_symbol_shapes()):
          coords = self.symbol_shape.get_symbol_shape_coords(symbol_val+1)
          values[symbol_val] = {}
          for x,y in coords:
            values[symbol_val][(x,y)] = pixels[x_coord + x, y_coord + y]

        extracted_datum = self.encoding_shape_translator.shapes_to_encoding(
          self.symbol_fill_translator.fill_to_symbol(values))
        extracted_data += extracted_datum
    return extracted_data