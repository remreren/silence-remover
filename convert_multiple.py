import argparse
import os
import time
from convert import convert

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", required=True, type=str, help="Input folder")
parser.add_argument("-o", "--output", required=True, type=str, help="Output folder")

args = parser.parse_args()

input_folder = args.input
output_folder = args.output

cwd_checkpoint = os.getcwd()
videos = []

os.chdir(input_folder)
for cur, _, files in os.walk('.'):
    for fl in files:
        if fl.endswith(".mp4"):
            videos.append({'output_path':os.path.join(cur, fl), 'input_path': os.path.join(os.path.abspath(cur), fl)})

os.chdir(cwd_checkpoint)

if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
    os.mkdir(output_folder)

os.chdir(output_folder)

start_time = time.time()

for fl in videos:
    bn = os.path.basename(fl['output_path'])
    fn = os.path.splitext(bn)[0]
    temp_folder = os.path.join(os.path.dirname(fl['output_path']), fn + '_temp')

    if not os.path.exists(os.path.dirname(fl['output_path'])):
        os.mkdir(os.path.dirname(fl['output_path']))

    convert(fl['input_path'], fl['output_path'], temp_folder=temp_folder)

total_duration = time.time() - start_time
seconds = total_duration % 60
mins = (total_duration // 60) % 60
hours = (total_duration // 3600) % 24

print(f"The process took {str(int(hours))} hours, {str(int(mins))} minutes, {seconds} seconds.")