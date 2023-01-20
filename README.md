# python_downloader

Downloading files using Python

## file_downloader.py

#### implement

The requests library can be used to initiate network requests. However, if it is used to download large files, single thread downloading cannot make good use of the width. It would be better to change to multi thread downloading.

1. When we request to download a file, we can use the head request to see how big the file is. The "Content Length" field in the response header represents the number of bytes of the file.
2. After the file size is obtained, it is divided into multiple data blocks according to the number of threads, that is, each thread requests a part, and the download range is specified in the "Range" field of the request header.
3. Since the same process writes to a file at the same time, be sure to lock it.
4. When using the requests library to download, the parameter must specify stream=True, or it will be bad if it is fully loaded into the memory.
5. If one of the blocks fails to download, it is equivalent to the failure of the whole file. However, I still want to try to download the file twice before it is determined to fail.

#### lib

```python
pip install requests
```

## m3u8_downloader.py

#### implement

M3u8 is a way to transmit data. For example, a 20 minute full video is divided into more than 1000 short videos of one or two seconds. When the client plays the video, it feels continuous. But if you want to download this video, you should download all of the more than 1000 short videos and then splice them into a complete video

- **m3u8 file**. M3u8 is generally a file ending in m3u8. If it is a browser, you can click F12 to open DevTools to capture the full link of m3u8. After downloading, extract the uri of all video segments. To facilitate operation, we can use the m3u8 library.
- **Encryption**. Some m3u8 are encrypted, but the URL of the secret key will be given in the file. The secret key can be obtained upon request. The secret key is generally a string consisting of numbers and letters. The general encryption algorithm is AES-128. We need to use the pycryptodome library to decrypt the encrypted video.
- **Merge videos**. The copy command provided with the Windows system can merge videos, but the merged videos may have problems, so it is recommended to use ffmpeg to merge.

#### lib

```python
pip install requests
pip install fake_useragent
pip install m3u8
pip install pycryptodome
pip install tqdm
```