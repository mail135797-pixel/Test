#!/bin/bash
ffmpeg -i video_processing/costco_video.mp4 -t 300 -vf "fps=0.2" video_processing/frame_%04d.jpg
