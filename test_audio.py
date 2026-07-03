from downloader import download_audio

try:
    result = download_audio("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "128")
    print(result)
except Exception as e:
    print(f"ERROR: {e}")
