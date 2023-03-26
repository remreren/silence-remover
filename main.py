import argparse
import math
import librosa
import os
import re
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input")
parser.add_argument("-o", "--output")

args = parser.parse_args()

input_file = args.input
output_file = args.output

temp_audio_file = "./temp/audio.wav"

if os.path.exists("./temp"):
    shutil.rmtree("./temp")

os.mkdir("./temp")

os.system(f"ffmpeg -i {input_file} {temp_audio_file}")

def find_decibel_threshold(rms):
    mask = rms > 0.01 # mask to reduce 0.0 rms frequency
    masked_rms = rms[mask]

    q1 = np.percentile(masked_rms, 25)
    q3 = np.percentile(masked_rms, 75)

    iqr = q3 - q1 # interquantile range
    thr = iqr * 1.96 # zscore for %95 ci

    med = np.median(masked_rms) # median of rms'
    upb = med + thr # upperbound for outliers
    lwb = med - thr # lowerbound for outliers

    outlier_removing_mask = (masked_rms > lwb) & (masked_rms < upb)
    outliers_removed = masked_rms[outlier_removing_mask]

    max_rms = np.max(outliers_removed)
    # fig, ax = plt.subplots(2, 2)

    # ax[0, 0].hist(masked_rms, bins=100)
    # ax[0, 0].set_title("masked rms")

    # ax[0, 1].hist(rms[0], bins=100)
    # ax[0, 1].set_title("rms")

    # ax[1, 0].hist(outliers_removed, bins=100)
    # ax[1, 0].set_title("outliers_removed")

    # fig.show()
    # input()

    return (10 * math.log10(max_rms) + 30)


ts, sr = librosa.load(temp_audio_file)
rms = librosa.feature.rms(y = ts)

threshold_db = find_decibel_threshold(rms)
# attack_time = 0.01
# release_time = 0.1
# padding_value = 0.1

command = [
    "ffmpeg", "-i", temp_audio_file, "-af",
    f"silencedetect=noise=0.001:n={-threshold_db}dB",
    "-f", "null", "-"
]

out = subprocess.check_output(command, stderr=subprocess.STDOUT)

sections = []
start_matcher = re.compile(r"^\[silencedetect\s[^]]+\]\ssilence_start\:\s([0-9\.]+)")
end_matcher = re.compile(r"^\[silencedetect\s[^]]+\]\ssilence_end\:\s([0-9\.]+)\s\|\ssilence_duration\:\s([0-9\.]+)")

for line in out.splitlines():
    line = line.decode('utf-8')

    start_matches = start_matcher.match(line)
    end_matches = end_matcher.match(line)

    if start_matches != None:
        start = start_matches.group(1)

    if end_matches != None:
        end = end_matches.group(1)
        dur = end_matches.group(2)
        sections.append((start, end, dur))

sections_inverted = []
for i in range(0, len(sections) - 1):
    sections_inverted.append((sections[i][1], sections[i + 1][0]))

cuts = "+".join([f"between(t,{sec[0]},{sec[1]})" for sec in sections_inverted])
audio_cuts = "aselect='" + cuts + "', asetpts=N/SR/TB"
video_cuts = "select='" + cuts + "', setpts=N/FRAME_RATE/TB"

with open("./temp/audio.txt", "w+") as fp:
    fp.write(audio_cuts)

with open("./temp/video.txt", "w+") as fp:
    fp.write(video_cuts)

os.system(f"ffmpeg -i {input_file} -filter_script:a ./temp/audio.txt -filter_script:v ./temp/video.txt {output_file}")
# plt.hist(res, bins=100)

# print(res)

# plt.xlabel("Value")
# plt.ylabel("Freq")
# plt.show()