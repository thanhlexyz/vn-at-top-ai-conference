"""The Short as an MP4: each frame held while its narration plays, captions burned in.

    python3 video/make_short.py && python3 video/make_preview.py [--lang vi|en] [--voice] [--speed 1.15]
        [--music "Local Forecast - Elevator.mp3"] [--music-db -12]

Without --voice the video is silent and timed by the estimated speaking rate.
With --voice the Vietnamese narration is read by the Google Translate voice (gTTS, which sends the text to Google),
one clip per line, cached in video/short/audio/. Frames and both subtitle files are then re-timed to the real audio.

Writes video/short/preview.<lang>.mp4 (silent) or video/short/short.<lang>.mp4 (with voice), 1080x1920, 30 fps.
"""
import hashlib
import json
import subprocess
import sys

import make_short as ms

args = sys.argv[1:]
lang = args[args.index("--lang") + 1] if "--lang" in args else "vi"
speed = float(args[args.index("--speed") + 1]) if "--speed" in args else 1.15
voice = "--voice" in args
track = args[args.index("--music") + 1] if "--music" in args else None   # a file name in video/music/
MUSIC_DB = float(args[args.index("--music-db") + 1]) if "--music-db" in args else -12.0
out_dir = ms.OUT
n = ms.compute()
spec = json.loads((ms.ROOT / "video" / "short.json").read_text(encoding="utf-8"))
timed, total = ms.timeline(spec["lines"], n)
GAP = 0.35   # silence between lines
MUSIC_CREDIT = """Nhạc nền / Music: "{title}" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0 License
http://creativecommons.org/licenses/by/4.0/"""


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True, check=True).stdout)


def speak(text):
    """One narration line as a WAV clip at the chosen speed, cached by its text and speed."""
    from gtts import gTTS
    audio = out_dir / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{speed}|{text}|{json.dumps(spec.get('tts_pronounce', {}), sort_keys=True)}".encode()).hexdigest()[:12]
    wav = audio / f"{key}.wav"
    if not wav.exists():
        mp3 = audio / f"{key}.mp3"
        spoken = text
        for written, said in spec.get("tts_pronounce", {}).items():   # how the voice should say a term
            spoken = spoken.replace(written, said)
        gTTS(spoken, lang="vi").save(str(mp3))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-af", f"atempo={speed}", "-ar", "44100", "-ac", "1",
                        str(wav)], check=True)
        mp3.unlink()
    return wav


narration = None
if voice:
    clips, t = [], 0.4
    for ln in timed:
        wav = speak(ln["vi"])
        d = duration(wav)
        ln["start"], ln["end"] = t, t + d
        clips.append((wav, t))
        t += d + GAP
    total = t
    # one track: every clip placed at its start time
    narration = out_dir / "audio" / "narration.wav"
    inputs = sum((["-i", str(w)] for w, _ in clips), [])
    delays = ";".join(f"[{k}]adelay={int(s * 1000)}|{int(s * 1000)}[a{k}]" for k, (_, s) in enumerate(clips))
    mix = "".join(f"[a{k}]" for k in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[out]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", f"{delays};{mix}", "-map", "[out]",
                    "-t", f"{total + 1.5:.2f}", str(narration)], check=True)
    if track:   # jazz underneath, ducked further while the voice speaks, faded in and out
        music = ms.ROOT / "video" / "music" / track
        bed = out_dir / "audio" / "with_music.wav"
        end = total + 1.5
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
                        "-filter_complex",
                        f"[1:a]atrim=0:{end:.2f},volume={MUSIC_DB}dB,afade=t=in:d=1.5,afade=t=out:st={end - 2.5:.2f}:d=2.5,"
                        f"aresample=44100,aformat=channel_layouts=stereo[m];"
                        f"[0:a]aformat=channel_layouts=stereo,asplit=2[v][sc];"
                        f"[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];"
                        f"[v][duck]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.95[out]",
                        "-map", "[out]", "-t", f"{end:.2f}", str(bed)], check=True)
        narration = bed
        credit = MUSIC_CREDIT.format(title=music.stem)
        yt = out_dir / "youtube.md"
        text = yt.read_text(encoding="utf-8").split("\n## Music credit")[0].rstrip()
        yt.write_text(text + "\n\n## Music credit (paste at the end of the description)\n\n" + credit + "\n", encoding="utf-8")
    for lg in ("vi", "en"):   # subtitles follow the real voice
        (out_dir / f"subtitles.{lg}.srt").write_text(ms.srt(timed, lg), encoding="utf-8")

# how long each frame stays on screen: from its first line's start to the next frame's first line
spans = []
for ln in timed:
    if spans and spans[-1][0] == ln["frame"]:
        spans[-1][2] = ln["end"]
    else:
        spans.append([ln["frame"], ln["start"], ln["end"]])
spans[0][1] = 0.0
for k in range(len(spans) - 1):
    spans[k][2] = spans[k + 1][1]
spans[-1][2] = total + 1.5   # hold the last frame a little
length = spans[-1][2]

concat = out_dir / "preview_frames.txt"
lines = []
for name, start, end in spans:
    png = out_dir / "frames" / f"{ms.FRAMES.index(name) + 1:02d}-{name}.png"
    lines += [f"file '{png}'", f"duration {end - start:.3f}"]
lines.append(lines[-2])   # the concat demuxer needs the last file twice
concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

srt = out_dir / f"subtitles.{lang}.srt"
# libass scales these from a 288-line canvas: 8 is about 54 px on 1920, MarginV 20 about 135 px from the bottom
style = ("FontName=Noto Sans,FontSize=8,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00202020,"
         "BackColour=&H20202020,BorderStyle=4,Outline=1,Shadow=0,MarginV=20,MarginL=12,MarginR=12,Alignment=2")
video = out_dir / (f"short.{lang}.mp4" if voice else f"preview.{lang}.mp4")
cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat)]
if narration:
    cmd += ["-i", str(narration)]
cmd += ["-vf", f"fps=30,format=yuv420p,subtitles={srt}:force_style='{style}'", "-t", f"{length:.2f}",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium"]
if narration:
    cmd += ["-c:a", "aac", "-b:a", "160k", "-map", "0:v", "-map", "1:a"]
cmd += ["-movflags", "+faststart", str(video)]
subprocess.run(cmd, check=True)
concat.unlink()
print(f"{video.relative_to(ms.ROOT)}: {length:.0f} s, {len(spans)} frames, captions: {lang}, voice: {'yes' if voice else 'no'}")
