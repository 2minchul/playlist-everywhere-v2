from typing import NamedTuple


class CsvRow(NamedTuple):
    vendor_name: str
    playlist_name: str
    song_id: str
    title: str
    artist: str

    @classmethod
    def header(cls):
        return ['음원사', '플레이리스트 이름', '노래 id', '제목', '아티스트']
