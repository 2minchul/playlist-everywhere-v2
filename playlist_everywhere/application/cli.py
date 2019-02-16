import csv
import json
import os
import sys

import pyperclip
from PyInquirer import prompt as _prompt
from tqdm import tqdm

from playlist_everywhere.application.common import BaseApplication
from playlist_everywhere.application.enums import CsvRow
from playlist_everywhere.vendor import BaseSong, ClientNotAuthenticated, GenieClient, MelonClient
from playlist_everywhere.vendor.bugs import BugsClient
from playlist_everywhere.vendor.enums import PlaylistType, SigninMethod


def prompt(questions, answers=None, **kwargs) -> dict:
    answers = _prompt(questions, answers, **kwargs)
    if not answers:
        raise KeyboardInterrupt()
    return answers


class CliApplication(BaseApplication):
    VENDOR_DICT = {
        'melon': MelonClient,
        'genie': GenieClient,
        'bugs': BugsClient,
    }

    def get_vendor_client(self, vendor_name: str):
        return self.VENDOR_DICT[vendor_name]()

    @classmethod
    def login(cls, vendor_client):
        sys.stderr.write("로그인이 필요합니다.\n")
        while True:
            answer = prompt([
                {
                    'type': 'list',
                    'name': 'method',
                    'message': '로그인 방법을 선택 해 주세요.',
                    'choices': SigninMethod.all(),
                }
            ])
            method = answer['method']
            supported_signin_methods = vendor_client.get_supported_signin_methods()
            if method not in supported_signin_methods:
                sys.stderr.write("아직 지원하지 않는 로그인 방법 입니다.\n")
                continue
            break

        try:
            if method == SigninMethod.id_pw:
                credentials = prompt([
                    {
                        'type': 'input',
                        'name': 'account_id',
                        'message': '계정 아이디/이메일을 입력해주세요:',
                        'validate': lambda val: len(val) > 0 or '아이디/이메일을 올바르게 입력해주세요.',
                    },
                    {
                        'type': 'password',
                        'name': 'account_password',
                        'message': '계정 비밀번호를 입력해주세요:',
                        'validate': lambda val: len(val) > 0 or '비밀번호를 올바르게 입력해주세요.',
                    }
                ])
                vendor_client.signin(
                    account_id=credentials['account_id'],
                    account_password=credentials['account_password'],
                )
            elif method == SigninMethod.cookies:
                cookies = {}
                while True:
                    if os.path.isfile('cookies.txt'):
                        try:
                            with open('cookies.txt', 'r') as f:
                                cookies_list = json.load(f)
                            cookies = {cookie['name']: cookie['value'] for cookie in cookies_list
                                       if cookie['domain'] == '.bugs.co.kr'}
                            if cookies:
                                vendor_client.signin(cookies=cookies)
                                break
                        except:
                            pass
                    prompt([
                        {
                            'type': 'input',
                            'name': 'enter',
                            'message': 'EditThisCookie 확장프로그램을 이용해서 쿠키를 클립보드에 복사한 후에 엔터를 눌러주세요.',
                        }
                    ])
                    try:
                        text = pyperclip.paste()
                        cookies_list = json.loads(text)
                        cookies = {cookie['name']: cookie['value'] for cookie in cookies_list}
                    except (KeyError, json.JSONDecodeError):
                        continue
                    break
                vendor_client.signin(cookies=cookies)

            sys.stdout.write("로그인 되었습니다.\n")
        except Exception as e:
            sys.stderr.write(f"오류가 발생했습니다: {e}\n")

    def run(self):
        try:
            answers = prompt([
                {
                    'type': 'list',
                    'name': 'action',
                    'message': '실행할 작업을 선택하세요.',
                    'choices': ['download', 'upload', ]
                },
                {
                    'type': 'list',
                    'name': 'vendor',
                    'message': '서비스 제공사를 선택하세요.',
                    'choices': list(self.VENDOR_DICT.keys()),
                }
            ])
            getattr(self, answers['action'])(answers['vendor'])
        except KeyboardInterrupt:
            sys.stdout.write("취소되었습니다.\n")

    def download(self, vendor_name: str):
        vendor_client = self.get_vendor_client(vendor_name)
        supported_playlist_types = vendor_client.get_supported_playlist_types()

        flag = False
        while not flag:
            playlist_id = ''
            try:
                answers = prompt([
                    {
                        'type': 'list',
                        'name': 'playlist_type',
                        'message': '플레이리스트 타입을 선택하세요.',
                        'choices': supported_playlist_types,
                    },
                ])
                playlist_type = answers['playlist_type']
                if playlist_type in (PlaylistType.my, PlaylistType.my_all):
                    while not vendor_client.is_signin:
                        self.login(vendor_client)

                if playlist_type != PlaylistType.my_all:
                    answers = prompt([
                        {
                            'type': 'input',
                            'name': 'playlist_id',
                            'message': '다운로드할 플레이리스트를 입력해주세요. (ID 형식)',
                            'validate': lambda val: val.isnumeric() or '올바른 대상을 입력해주세요.',
                        }
                    ])
                    playlist_id = answers['playlist_id']

                answers = prompt([
                    {
                        'type': 'input',
                        'name': "file_name",
                        'message': '저장할 파일명을 입력해주세요.',
                        'validate': lambda val: len(val) > 0 or '파일명을 올바르게 입력해주세요.',
                    }
                ])
                file_name = answers['file_name']

                with tqdm(total=100) as progress_bar:
                    progress_bar.set_description("플레이리스트 파싱중")
                    playlist = vendor_client.get_playlist(playlist_type, playlist_id)
                    progress_bar.update(60)
                    progress_bar.set_description("파일 변환중")
                    with open(file_name, "w", encoding='utf-8-sig', newline='') as playlist_file:
                        writer = csv.writer(playlist_file)
                        writer.writerow(CsvRow.header())
                        for song in playlist:  # type: BaseSong
                            row = CsvRow(
                                vendor_name=vendor_name,
                                playlist_name=song.playlist_name,
                                song_id=song.id,
                                title=song.title,
                                artist=song.artist,
                            )
                            writer.writerow(row)
                    progress_bar.update(40)
                sys.stdout.write("===== 다운로드 결과 =====\n")
                sys.stdout.write(f"다운로드 곡 수: {len(playlist)}곡\n")
                sys.stdout.write(f"파일: {os.path.realpath(file_name)}\n")
                sys.stdout.write("====================")
                flag = True

            except ClientNotAuthenticated:
                self.login(vendor_client)

            except NotImplementedError:
                sys.stderr.write(f"현재 선택하신 제공사에는 준비중인 기능입니다.\n")
                flag = True

            except Exception as e:
                print(type(e))
                sys.stderr.write(f"오류가 발생했습니다: {e}\n")

    def upload(self, vendor_name: str):
        vendor_client = self.VENDOR_DICT[vendor_name]()

        while not vendor_client.is_signin:
            self.login(vendor_client)

        try:
            answers = prompt([
                {
                    'type': 'input',
                    'name': 'file_name',
                    'message': '업로드할 플레이리스트 파일명을 입력해주세요. (경로 포함)',
                    'validate': lambda val: os.path.isfile(val) or '올바른 파일을 입력해주세요.',
                }
            ])
            with tqdm(total=100) as progress_bar:
                progress_bar.set_description("파일 불러오는중")

                playlist_vendor = None
                song_list = []
                with open(answers['file_name'], "r", encoding='utf-8-sig', newline='') as playlist_file:
                    reader = csv.reader(playlist_file)
                    next(reader)
                    for row_args in reader:
                        row = CsvRow(*row_args)
                        song_list.append(BaseSong(row.song_id, row.title, row.artist, row.playlist_name))

                progress_bar.update(10.0)
                progress_bar.set_description("음원 검색중")

                matched_song = []
                unmatched_song = []
                progress_per_match = 50 / len(song_list)
                playlists = {}
                if vendor_name == playlist_vendor:
                    matched_song = song_list
                else:
                    for saved_song in song_list:
                        playlists[saved_song.playlist_name] = ''
                        search_result = vendor_client.search_song(vendor_client.get_keyword_from_song(saved_song))
                        if search_result:
                            song: BaseSong = search_result[0]
                            song.playlist_name = saved_song.playlist_name
                            matched_song.append(song)
                        else:
                            unmatched_song.append(saved_song)
                        progress_bar.update(progress_per_match)

                progress_bar.set_description("플레이리스트 생성중")
                for playlist_name in playlists.keys():
                    new_playlist_id = vendor_client.create_personal_playlist(playlist_name)
                    playlists[playlist_name] = new_playlist_id

                progress_bar.update(10.0)
                progress_bar.set_description("플레이리스트 구성중")

                progress_per_add = 30 / len(matched_song)
                unregistered_song = []
                for song in matched_song:
                    try:
                        new_playlist_id = playlists[song.playlist_name]
                        vendor_client.add_song_to_personal_playlist(new_playlist_id, song)
                    except Exception:
                        unregistered_song.append(song)
                    progress_bar.update(progress_per_add)

            sys.stdout.write("===== 업로드 결과 =====\n")
            sys.stdout.write(f"불러온 곡 수: {len(song_list)}곡\n")
            sys.stdout.write(f"매치된 곡 수: {len(matched_song)}\n")

            with open('unregistered_song.csv', 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(CsvRow.header())

                for song in unmatched_song:
                    row = CsvRow(
                        vendor_name=vendor_name,
                        playlist_name=song.playlist_name,
                        song_id=song.id,
                        title=song.title,
                        artist=song.artist,
                    )
                    writer.writerow(row)
                    sys.stdout.write(f">>> Not Found - {song}\n")

                sys.stdout.write(f"등록된 곡 수: {len(matched_song) - len(unregistered_song)}곡\n")

                for song in unregistered_song:
                    row = CsvRow(
                        vendor_name=vendor_name,
                        playlist_name=song.playlist_name,
                        song_id=song.id,
                        title=song.title,
                        artist=song.artist,
                    )
                    writer.writerow(row)
                    sys.stdout.write(f">>> Add failed - {str(song)}\n")
            sys.stdout.write("====================")

        except NotImplementedError:
            sys.stderr.write(f"현재 선택하신 제공사에는 준비중인 기능입니다.")

        except Exception as e:
            sys.stderr.write(f"오류가 발생했습니다: {e}")
