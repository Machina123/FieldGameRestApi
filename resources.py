"""
Moduł zawierający zasoby interfejsu API aplikacji
"""
from flask import jsonify
from flask_jwt_extended import (create_access_token, create_refresh_token, jwt_required, jwt_refresh_token_required,
                                get_jwt_identity, get_raw_jwt, set_access_cookies, set_refresh_cookies,
                                unset_jwt_cookies,
                                get_jwt_claims)
from flask_restful import Resource, reqparse

from app import db
from models import UserModel, RevokedTokenModel, GameModel, RiddleModel, ScoreboardEntryModel

parser = reqparse.RequestParser()
parser.add_argument('username', help='This field cannot be blank', required=True)
parser.add_argument('password', help='This field cannot be blank', required=True)

game_parser = reqparse.RequestParser()
game_parser.add_argument('title', help='This field cannot be blank', required=True)
game_parser.add_argument('description', help='This field cannot be blank', required=True)
game_parser.add_argument('riddles', help='This field cannot be blank', required=True)

riddle_parser = reqparse.RequestParser()
riddle_parser.add_argument('game_id', help='This field cannot be blank', required=True)
riddle_parser.add_argument('riddle_no', help='This field cannot be blank', required=True)
riddle_parser.add_argument('latitude', help='This field cannot be blank', required=True)
riddle_parser.add_argument('longitude', help='This field cannot be blank', required=True)
riddle_parser.add_argument('description', help='This field cannot be blank', required=True)
riddle_parser.add_argument('radius', help='This field cannot be blank', required=True)
riddle_parser.add_argument('dominant_object', help='This field cannot be blank', required=True)


class UserRegistration(Resource):
    """
    Zasób odpowiadający za zarejestrowanie użytkownika.

    Udziela odpowiedzi tylko na zapytania wysłąne metodą POST.
    """
    def post(self):
        data = parser.parse_args()

        if UserModel.find_by_username(data['username']):
            return {'message': f"User {data['username']} already exists"}

        new_user = UserModel(
            username=data['username'],
            password=UserModel.generate_hash(data['password'])
        )
        try:
            new_user.save_to_db()
            return {
                'message': f"User {data['username']} was created"
            }
        except:
            return {'message': 'Something went wrong'}, 500


class UserLogin(Resource):
    """
    Zasób odpowiadający za zalogowanie użytkownika i przydzielenie mu żetonu dostępowego JWT (JSON Web Token).

    Udziela odpowiedzi na zapytania wysłane metodą POST.
    """
    def post(self):
        data = parser.parse_args()
        current_user = UserModel.find_by_username(data['username'])

        if not current_user:
            return {'message': f'User {data["username"]} doesn\'t exist'}

        if UserModel.verify_hash(data['password'], current_user.password):
            access_token = create_access_token(identity=data['username'])
            refresh_token = create_refresh_token(identity=data['username'])
            resp = jsonify({
                'message': f'Logged in as {current_user.username}',
                'access_token': access_token,
                'refresh_token': refresh_token
            })
            set_access_cookies(resp, access_token)
            set_refresh_cookies(resp, refresh_token)
            return resp
        else:
            return {'message': 'Wrong credentials'}


class UserLogout(Resource):
    """
    Zasób odpowiadający za wylogowanie użytkownika i unieważnienie żetonu dostępowego JWT (JSON Web Token).

    Udziela odpowiedzi na zapytania wysłane metodą POST zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_refresh_token_required
    def post(self):
        jti = get_raw_jwt()['jti']
        try:
            revoked_token = RevokedTokenModel(jti=jti)
            revoked_token.add()
            resp = jsonify({'message': 'Refresh token has been revoked'})
            unset_jwt_cookies(resp)
            return resp
        except Exception as e:
            print(e)
            return {'message': 'Something went wrong'}, 500


class TokenRefresh(Resource):
    """
    Zasob odpowiadający za odświeżenie żetonu JWT (JSON Web Token).

    Udziela odpowiedzi na zapytania wysłane metodą POST zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_refresh_token_required
    def post(self):
        current_user = get_jwt_identity()
        access_token = create_access_token(identity=current_user)
        resp = jsonify({'access_token': access_token})
        set_access_cookies(resp, access_token)
        return resp


class GameDetailsResource(Resource):
    """
    Zasób odpowiadający za wyświetlenie szczegółów dotyczących wybranej gry

    Udziela odpowiedzi na zapytania wysłane metodą GET zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_required
    def get(self, game_id):
        return GameModel.serialize([GameModel.find_by_id(game_id)])


class RiddleListResource(Resource):
    """
    Zasób odpowiadający za wyświetlenie zagadek powiązanych z wybraną grą

    Udziela odpowiedzi na zapytania wysłane metodą GET zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_required
    def get(self, game_id):
        return RiddleModel.print_riddles_for_game(game_id)


class UserGamesStatusResource(Resource):
    """
    Zasób odpowiadający za wyświetlenie postępu aktualnie zalogowanego użytkownika we wszystkich grach

    Udziela odpowiedzi na zapytania wysłane metodą GET zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_required
    def get(self):
        current_user = get_jwt_identity()
        return ScoreboardEntryModel.print_by_user(current_user)


class GameProgressResource(Resource):
    """
    Zasób odpowiadający za wyświetlenie postępu aktualnie zalogowanego użytkownika w wybranej grze

    Udziela odpowiedzi na zapytania wysłane metodą GET zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_required
    def get(self, game_id):
        current_user = get_jwt_identity()
        return ScoreboardEntryModel.print_by_user_and_game(current_user, game_id)


class GameAdvancementResource(Resource):
    """
    Zasób odpowiadający za aktualizację postępu aktualnie zalogowanego użytkownika we wskazanej grze

    Udziela odpowiedzi na zapytania wysłane metodą POST zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_required
    def post(self, game_id):
        import datetime as dt
        current_user = get_jwt_identity()
        current_progress = ScoreboardEntryModel.filter_by_user_and_game(current_user, game_id)
        current_game = GameModel.find_by_id(game_id)
        if current_progress.current_riddle + 1 > current_game.riddles:
            current_progress.finished = True
            current_progress.time_end = dt.datetime.now()
        else:
            current_progress.current_riddle = ScoreboardEntryModel.current_riddle + 1
        db.session.commit()
        return ScoreboardEntryModel.serialize([current_progress])


class GameStartResource(Resource):
    """
    Zasób odpowiadający za dołączenie aktualnie zalogowanego użytkownika do nowej gry

    Udziela odpowiedzi na zapytania wysłane metodą POST zawierające "ciasteczko" z żetonem JWT.
    """
    @jwt_required
    def post(self, game_id):
        username = get_jwt_identity()
        user = UserModel.find_by_username(username)
        is_game_started = ScoreboardEntryModel.filter_by_user_and_game(username, game_id)
        print(is_game_started)
        if is_game_started is None:
            game = ScoreboardEntryModel(
                user_id=user.id,
                game_id=game_id
            )
            game.save_to_db()
        return ScoreboardEntryModel.serialize(ScoreboardEntryModel.filter_by_user(username))


class StatisticsResource(Resource):
    """
    Zasób odpowiadający za pobranie postępu wszystkich graczy we wszystkich grach.

    Udziela odpowiedzi na zapytania wysłane metodą GET.
    """
    def get(self):
        import datetime as dt
        out_entries = []
        scoreboard = ScoreboardEntryModel.get_all_entries()
        for sbentry in scoreboard:
            user = UserModel.find_by_id(sbentry.user_id)
            game = GameModel.find_by_id(sbentry.game_id)
            elapsed_seconds = (sbentry.time_end - sbentry.time_begin).total_seconds() \
                if sbentry.time_end else (dt.datetime.now() - sbentry.time_begin).total_seconds()
            entry = {
                "username": user.username,
                "game": game.title,
                "current_riddle": sbentry.current_riddle,
                "finished": sbentry.finished,
                "time_begin": int(sbentry.time_begin.timestamp() * 1000),
                "elapsed_seconds": elapsed_seconds
            }
            out_entries.append(entry)
        return {"entries": out_entries}


class AllGamesResource(Resource):
    """
    Zasób odpowiadający za pobranie wszystkich dostępnych na serwerze gier.

    Udziela odpowiedzi na zapytania wysłane metodą GET.
    """
    def get(self):
        return GameModel.return_all()


class GameCreationResource(Resource):
    """
    Zasób odpowiadający za dodanie nowej gry

    Udziela odpowiedzi na zapytania wysłane metodą PUT. Wymaga posiadania praw administratora aplikacji.
    """
    @jwt_required
    def put(self):
        claims = get_jwt_claims()
        if claims["admin"]:
            data = game_parser.parse_args()
            newgame = GameModel(
                title=data["title"],
                description=data["description"],
                riddles=int(data["riddles"])
            )
            newgame.save_to_db()
            return GameModel.serialize([newgame])
        else:
            return {"message": "Admin privileges are required to perform this action"}


class RiddleCreationResource(Resource):
    """
    Zasób odpowiadający za dodanie nowej zagadki.

    Udziela odpowiedzi na zapytania wysłane metodą PUT. Wymaga posiadania praw administratora aplikacji.
    """
    @jwt_required
    def put(self, game_id):
        claims = get_jwt_claims()
        if claims["admin"]:
            data = riddle_parser.parse_args()
            newriddle = RiddleModel(
                game_id=game_id,
                riddle_no=int(data["riddle_no"]),
                latitude=float(data["latitude"]),
                longitude=float(data["longitude"]),
                description=data["description"],
                radius=int(data["radius"]),
                dominant_object=data["dominant_object"]
            )
            newriddle.save_to_db()
            return RiddleModel.serialize([newriddle])
        else:
            return {"message": "Admin privileges are required to perform this action"}
