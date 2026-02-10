# import json
# import os
#
# from PIL import Image
#
# from pridexyz.image_processing import nine_slice_scale
#
# image = Image.open("./frame_bi.png").convert("RGBA")
#
# scaled_img = nine_slice_scale(image, 2, 2, 2, 2, 51, 36, tile=False, padding=(8, 8, 8, 8))
# scaled_img.save("test.png")
# scaled_img.show()
#
#
# def convert_list_to_map(file_path):
#     with open(file_path, 'r') as file:
#         data = json.load(file)
#
#     data_map = {item.pop('name'): item for item in data}
#
#     base, ext = os.path.splitext(file_path)
#     output_file = f"{base}2{ext}"
#
#     with open(output_file, 'w') as file:
#         json.dump(data_map, file, indent=4)
#
#     print(f"Converted data saved to: {output_file}")
#
#
# input_file = "../src/colors.json"
# convert_list_to_map(input_file)
