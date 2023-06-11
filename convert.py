import argparse
# import math
import librosa
import os
import re
import numpy as np
# import matplotlib.pyplot as plt
import subprocess
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", required=True, type=str, help="Input path")
parser.add_argument("-o", "--output", required=True, type=str, help="Output path")
parser.add_argument("-y", "--yes", action="store_true", help="Override automatically if the output file exists.")
parser.add_argument("-d", "--debug", action="store_true", help="Enables the debug mode that extracts the cuts and glues them together and saves to see if there is anything wrong")

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
    min_db = np.min(dbs_outliers_removed)
    
    return min_db * percentage

def find_silences(threshold_db, temp_audio_file, yes):
    command = [
        "ffmpeg", "-i", temp_audio_file, "-af",
        f"silencedetect=noise=0.001:n={threshold_db}dB",
        "-f", "null", "-"
    ]

    if yes:
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

def convert(input_file, output_file, temp_folder = "./temp", yes=False, debug=False):

    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)

    os.mkdir(temp_folder)

    temp_audio_file = os.path.join(temp_folder, "audio.wav")

    temp_audio = os.path.join(temp_folder, "audio.txt")
    temp_video = os.path.join(temp_folder, "video.txt")

    print(f"ffmpeg -i '{input_file}' '{temp_audio_file}'")
    os.system(f"ffmpeg -i '{input_file}' '{temp_audio_file}'")

    ts, sr = librosa.load(temp_audio_file)
    rms = librosa.feature.rms(y = ts)

    threshold_db = find_decibel_threshold(rms, 0.2)
    silences = find_silences(threshold_db, temp_audio_file, yes)

    sounds = invert_silences(silences)

    cuts = "+".join([f"between(t,{sec[0]},{sec[1]})" for sec in sounds])
    audio_cuts = "aselect='" + cuts + "', asetpts=N/SR/TB"
    video_cuts = "select='" + cuts + "', setpts=N/FRAME_RATE/TB"

    with open(temp_audio, "w+") as fp:
        fp.write(audio_cuts)

    with open(temp_video, "w+") as fp:
        fp.write(video_cuts)

    if not os.path.exists(os.path.dirname(output_file)):
        os.mkdir(os.path.dirname(output_file))
    os.system(f"ffmpeg {'-y ' if yes else ''}-i '{input_file}' -filter_script:a '{temp_audio}' -filter_script:v '{temp_video}' '{output_file}'")

    if debug:
        temp_debug_cuts=os.path.join(temp_folder, 'debug_cuts.txt')
        debug_cuts = "aselect='" + "+".join([f"between(t,{sec[0]},{sec[1]})" for sec in silences]) + "', asetpts=N/SR/TB"
        
        with open(temp_debug_cuts, "w+") as fp:
            fp.write(debug_cuts)
        
        debug_cuts = os.path.join(temp_folder, "debug_cuts.txt")
        debug_audio = os.path.join(temp_folder, "debug_audio.wav")
        os.system(f"ffmpeg -y -i '{temp_audio_file}' -filter_script:a '{debug_cuts}' '{debug_audio}'")

if __name__ == '__main__':
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output

    yes = args.yes
    debug = args.debug

    convert(input_file, output_file, yes=yes, debug=debug)
