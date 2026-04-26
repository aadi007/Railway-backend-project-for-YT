import math
from typing import List, Dict

class ChunkingEngine:

    @staticmethod
    def segment(transcript: List[Dict], window_sec: int = 60) -> List[Dict]:
        chunks = []
        current = []
        start_time = transcript[0]["start"]

        for entry in transcript:
            if entry["start"] - start_time <= window_sec:
                current.append(entry["text"])
            else:
                chunks.append({
                    "time": start_time,
                    "text": " ".join(current)
                })
                current = [entry["text"]]
                start_time = entry["start"]

        if current:
            chunks.append({
                "time": start_time,
                "text": " ".join(current)
            })

        return chunks

    @staticmethod
    def build_timestamps(chunks: List[Dict]) -> List[Dict]:
        def format_time(seconds):
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}:{str(s).zfill(2)}"

        return [
            {"time": format_time(c["time"]), "title": " "}
            for c in chunks
        ]

    @staticmethod
    def to_chunk_summary(chunks: List[Dict], max_chars=300) -> str:
        """
        Ultra low cost: compress each chunk
        """
        summaries = []
        for c in chunks[:12]:  # limit chunks
            text = c["text"][:max_chars]
            summaries.append(f"{int(c['time'])}s: {text}")
        return "\n".join(summaries)