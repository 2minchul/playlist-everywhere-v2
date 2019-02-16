#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import unicodedata
from typing import List

from bs4 import BeautifulSoup

from playlist_everywhere.vendor.common import BaseClient, BaseSong, ClientNotAuthenticated
from playlist_everywhere.vendor.enums import PlaylistType, SigninMethod


def normalize(s):
    s = unicodedata.normalize("NFKD", s)
    s = unicodedata.normalize('NFC', s)
    return s


class BugsClient(BaseClient):
    cookies: dict = None

    def get_supported_playlist_types(self) -> List[PlaylistType]:
        return [PlaylistType.my, PlaylistType.my_all]

    def get_supported_signin_methods(self):
        return [SigninMethod.cookies]

    def signin(self, account_id: str = '', account_password: str = '', cookies: dict = None):
        if account_id or account_password:
            raise ClientNotAuthenticated('아직 지원하지 않는 로그인 방식 입니다.')
        self.cookies = cookies
        response = self.session.post(
            "https://music.bugs.co.kr/bugsnotice/ajax/listcount",
            data={'notice_period': '3650', 'like_period': '7'},
            cookies=cookies,
        )
        if response.status_code != 200:
            raise ClientNotAuthenticated('로그인 정보가 올바르지 않습니다')
        data = response.json()
        if not data.get('isLogged'):
            raise ClientNotAuthenticated('로그인 정보가 올바르지 않습니다')

        self.is_signin = True

    def get_playlist(self, playlist_type: str, playlist_id: str) -> List[BaseSong]:
        if playlist_type not in (PlaylistType.my, PlaylistType.my_all):
            raise ValueError('올바르지 않은 플레이리스트 유형입니다.')
        if not self.is_signin:
            raise ClientNotAuthenticated('로그인이 필요합니다')

        if playlist_type == PlaylistType.my:
            return self.get_my_playlist(playlist_id)
        if playlist_type == PlaylistType.my_all:
            return self.get_all_my_playlists()
        return self.get_my_playlist(playlist_id)

    def find_all_my_playlists(self):
        response = self.session.get(
            'https://music.bugs.co.kr/user/library/ajax/myalbum/list?callback=&page=1',
            cookies=self.cookies,
        )
        response.raise_for_status()
        response_json = response.text.strip('()')
        data = json.loads(response_json)
        return {str(item['playlist_id']): item['title'] for item in data['myAlbumList']}

    def get_all_my_playlists(self) -> List[BaseSong]:
        playlists = self.find_all_my_playlists()
        result_songs = []
        for playlist_id, playlist_name in playlists.items():
            result_songs.extend(self.get_my_playlist(playlist_id))
        return result_songs

    def get_my_playlist(self, playlist_id: str) -> List[BaseSong]:
        playlists = self.find_all_my_playlists()
        if playlist_id not in playlists:
            raise ValueError('나의 플레이리스트 id 가 아닙니다')
        playlist_name = playlists[playlist_id]
        response = self.session.get(
            f'https://music.bugs.co.kr/user/library/ajax/myalbum/{playlist_id}',
            params={'playlistId': playlist_id, 'page': '1', 'size': '1000'},
            cookies=self.cookies,
        )
        with open('test.html', 'w') as f:
            f.write(response.text)
        parser = BeautifulSoup(response.text, 'html.parser')
        result_songs = []
        for song_item_dom in parser.find_all('tr', {'rowtype': 'track'}):
            song_id = song_item_dom.get('trackid')
            a_tag = song_item_dom.find('a', {'layer_type': 'USER_ALBUM_TRACK'})
            song_title = normalize(a_tag.get('track_title').strip())
            song_artist = normalize(a_tag.get('artist_disp_nm').strip())

            result_songs.append(BaseSong(song_id, song_title, song_artist, playlist_name))
        return result_songs
