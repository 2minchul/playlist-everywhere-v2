class SigninMethod:
    id_pw = 'id / pw'
    cookies = 'cookies'

    @classmethod
    def all(cls):
        return [cls.id_pw, cls.cookies]


class PlaylistType:
    my = '내 플레이리스트'
    my_all = '내 플레이리스트(전체)'
    dj = 'dj 플레이리스트'
