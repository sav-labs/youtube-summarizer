import yt_dlp
import os

def download_audio():
    url = input("Введите ссылку на YouTube-видео: ").strip()

    if not url:
        print("Ссылка не может быть пустой!")
        return

    try:
        # Настройка опций скачивания
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '%(title)s.%(ext)s',
            'quiet': False,
            'no_warnings': False
        }

        # Получаем информацию о видео
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'аудио')
            print(f"Скачивание аудио: {title}")

        # Скачиваем аудио
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Ищем скачанный файл в текущей директории
        mp3_file = None
        for file in os.listdir('.'):
            if file.endswith('.mp3') and title in file:
                mp3_file = file
                break
        
        if mp3_file:
            print(f"Аудио успешно скачано как '{mp3_file}'!")
        else:
            print("Аудио скачано успешно!")

    except Exception as e:
        print("Ошибка при скачивании:", e)

if __name__ == "__main__":
    download_audio()
