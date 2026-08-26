import os
import time
import glob
import hashlib
import asyncio
from typing import Optional
from core.models import Song
from core.database import Database
from utils.logger import log

class CacheService:
    def __init__(self, config, database: Database):
        self.config = config
        self.db = database
        self.cache_dir = os.path.join(os.getcwd(), "data", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._download_lock = asyncio.Lock()

    def get_cache_path(self, song: Song) -> Optional[str]:
        """Returns the local file path if a cached file exists for this song."""
        if not song or not song.path:
            return None
        fn_hash = hashlib.sha1(song.path.encode()).hexdigest()
        matches = glob.glob(os.path.join(self.cache_dir, f"{fn_hash}.*"))
        if matches:
            return matches[0]
        return None

    def is_cached(self, song: Song) -> bool:
        """Returns True if a valid local file exists for this song."""
        if not song or not song.path:
            return False
        
        # Check DB first for stored local path
        cached_data = self.db.get_cache(song.path)
        if cached_data:
            if song.title == song.path or (song.title and "[" in song.title):
                song.title = cached_data.get("title", song.title)
                song.uploader = cached_data.get("uploader", song.uploader)
                song.duration = cached_data.get("duration", song.duration)
                song.thumbnail_url = cached_data.get("thumbnail_url", song.thumbnail_url)

            if cached_data.get("local_path"):
                lp = cached_data["local_path"]
                if os.path.exists(lp):
                    return True
            
        # Fallback: Check deterministic path with any extension
        lp = self.get_cache_path(song)
        if lp and os.path.exists(lp):
            self.db.set_cache(
                url=song.path,
                title=song.title or "",
                uploader=song.uploader or "Unknown",
                duration=song.duration,
                thumbnail_url=song.thumbnail_url or "",
                local_path=lp
            )
            return True
            
        return False

    async def start_cache_download(self, song: Song):
        """Initiates a background download of the song to the local cache."""
        if self.is_cached(song):
            return
            
        asyncio.create_task(self._download_task(song))

    async def _download_task(self, song: Song):
        async with self._download_lock:
            if self.is_cached(song):
                return
            
            fn_hash = hashlib.sha1(song.path.encode()).hexdigest()
            target_path_template = os.path.join(self.cache_dir, f"{fn_hash}.%(ext)s")
            log.info(f"[CACHE] Starting download: {song.title}")
            
            try:
                cmd = [
                    self.config.ytdlp_path,
                    "-f", "bestaudio/best",
                    "--no-playlist",
                    "-o", target_path_template,
                    song.path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    actual_path = self.get_cache_path(song)
                    if actual_path:
                        log.info(f"[CACHE] Download complete: {song.title} -> {actual_path}")
                        self.db.set_cache(
                            url=song.path,
                            title=song.title or "",
                            uploader=song.uploader or "Unknown",
                            duration=song.duration,
                            thumbnail_url=song.thumbnail_url or "",
                            local_path=actual_path
                        )
                else:
                    err = stderr.decode().strip()
                    log.error(f"[CACHE] Download failed for {song.title}: {err}")
            except Exception as e:
                log.error(f"[CACHE] Download exception for {song.title}: {e}")

    def cleanup_cache(self):
        """Auto-cleanup of the cache based on size and expiry."""
        try:
            files = []
            for f in os.listdir(self.cache_dir):
                path = os.path.join(self.cache_dir, f)
                if os.path.isfile(path):
                    stats = os.stat(path)
                    files.append({
                        "path": path,
                        "size": stats.st_size,
                        "atime": stats.st_atime
                    })
            
            if not files:
                return
            
            files.sort(key=lambda x: x["atime"])
            
            now = time.time()
            expiry_seconds = self.config.cache_expiry_days * 86400
            size_limit = self.config.max_cache_size_mb * 1024 * 1024
            
            total_size = sum(f["size"] for f in files)
            deleted_count = 0
            
            # 1. Expiry cleanup
            files_to_check = list(files)
            for f in files_to_check:
                if (now - f["atime"]) > expiry_seconds:
                    try:
                        os.remove(f["path"])
                        total_size -= f["size"]
                        files.remove(f)
                        deleted_count += 1
                    except Exception as e:
                        log.warning(f"[CACHE] Could not delete expired file {f['path']}: {e}")
            
            # 2. Size cleanup (LRU)
            for f in files:
                if total_size <= size_limit:
                    break
                try:
                    os.remove(f["path"])
                    total_size -= f["size"]
                    deleted_count += 1
                except Exception as e:
                    log.warning(f"[CACHE] Could not delete LRU file {f['path']}: {e}")
            
            if deleted_count > 0:
                log.info(f"[CACHE] Auto-cleanup: {deleted_count} files removed.")
                
        except Exception as e:
            log.error(f"[CACHE] Auto-cleanup error: {e}")

    def clear_cache(self) -> int:
        """Deletes all files in the cache directory."""
        try:
            count = 0
            for f in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            
            self.db.clear_cache()
            log.info(f"[CACHE] Manual cache clear: {count} files removed.")
            return count
        except Exception as e:
            log.error(f"[CACHE] Error clearing cache: {e}")
            return 0

    def delete_cache_file(self, song: Song):
        """Deletes the local cache file for a specific song (ephemeral cache)."""
        if not song or not song.path:
            return
        
        path = self.get_cache_path(song)
        if path and os.path.exists(path):
            try:
                os.remove(path)
                log.info(f"[CACHE] Ephemeral deletion: {song.title}")
                self.db.set_cache(
                    url=song.path,
                    title=song.title or "",
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or "",
                    local_path=None
                )
            except Exception as e:
                log.warning(f"[CACHE] Could not delete ephemeral file {path}: {e}")
