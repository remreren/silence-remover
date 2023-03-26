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
parser.add_argument("-i", "--input", required=True, type=str)
parser.add_argument("-o", "--output", required=True, type=str)
parser.add_argument("-y", "--yes", action="store_true")
parser.add_argument("-d", "--debug", action="store_true")

args = parser.parse_args()

input_file = args.input
output_file = args.output

temp_audio_file = "./temp/audio.wav"

if os.path.exists("./temp"):
    shutil.rmtree("./temp")

os.mkdir("./temp")
os.system(f"ffmpeg -i {input_file} {temp_audio_file}")

def find_decibel_threshold(rms, percentage):
    dbs  = librosa.power_to_db(rms)[0]

    q1 = np.percentile(dbs, 25)
    q3 = np.percentile(dbs, 75)

    iqr = q3 - q1 # interquantile range
    thr = iqr * 1.96 # zscore for %95 ci

    med = np.median(dbs) # median of rms'
    upb = med + thr # upperbound for outliers
    lwb = med - thr # lowerbound for outliers

    dbs_outliers_removed = dbs[(dbs > lwb) & (dbs < upb)]

    # fig, ax = plt.subplots(2, 2)

    # ax[0, 0].hist(dbs, bins=100)
    # ax[0, 0].set_title("dbs")
    # ax[0, 1].hist(rms[0], bins=100)
    # ax[0, 1].set_title("rms")

    # ax[1, 1].hist(dbs_outliers_removed, bins=100)
    # ax[1, 1].set_title("decibels outliers removed")

    # fig.show()
    # input()

    min_db = np.min(dbs_outliers_removed)

    return min_db * percentage

def find_silences(threshold_db):
    command = [
        "ffmpeg", "-i", temp_audio_file, "-af",
        f"silencedetect=noise=0.001:n={threshold_db}dB",
        "-f", "null", "-"
    ]

    if args.yes:
        command.insert(1, "-y")
        print(command)

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

    return sections

def invert_silences(silences):
    silences_inverted = []
    for i in range(0, len(silences) - 1):
        silences_inverted.append((silences[i][1], silences[i + 1][0]))

    return silences_inverted

ts, sr = librosa.load(temp_audio_file)
rms = librosa.feature.rms(y = ts)

threshold_db = find_decibel_threshold(rms, 0.2)
silences = find_silences(threshold_db)
# attack_time = 0.01
# release_time = 0.1
# padding_value = 0.1

sounds = invert_silences(silences)

cuts = "+".join([f"between(t,{sec[0]},{sec[1]})" for sec in sounds])
audio_cuts = "aselect='" + cuts + "', asetpts=N/SR/TB"
video_cuts = "select='" + cuts + "', setpts=N/FRAME_RATE/TB"

with open("./temp/audio.txt", "w+") as fp:
    fp.write(audio_cuts)

with open("./temp/video.txt", "w+") as fp:
    fp.write(video_cuts)

os.system(f"ffmpeg {'-y ' if args.yes else ''}-i {input_file} -filter_script:a ./temp/audio.txt -filter_script:v ./temp/video.txt {output_file}")

if args.debug:
    debug_cuts = "aselect='" + "+".join([f"between(t,{sec[0]},{sec[1]})" for sec in silences]) + "', asetpts=N/SR/TB"
    
    with open("./temp/debug_cuts.txt", "w+") as fp:
        fp.write(debug_cuts)
    
    os.system(f"ffmpeg -y -i {temp_audio_file} -filter_script:a ./temp/debug_cuts.txt ./temp/debug_audio.wav")