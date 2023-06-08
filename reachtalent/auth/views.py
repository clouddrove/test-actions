import json

import jwt
from flask import (
    Flask, Blueprint, Response, redirect, request, abort, current_app, g
)
from flask_dance.consumer import (
    oauth_authorized, oauth_error,
    OAuth2ConsumerBlueprint, OAuth2Session
)
from flask_dance.consumer.storage import NullStorage
from flask_dance.contrib.facebook import make_facebook_blueprint
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.contrib.linkedin import make_linkedin_blueprint
from marshmallow import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm.exc import NoResultFound as OrmNoResultFound

from . import commands
from . import email
from . import tokens
from .models import db, User, AuthProvider, UserProfile
from .schema import (
    LoginRequest, LoginResponse,
    SignupRequest, SignupResponse,
    EmailVerifyRequest, EmailVerifyResponse,
    SendForgotPasswordRequest, SendForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse,
    SendInviteRequest, SendInviteResponse,
    AuthSessionRequest, AuthSessionResponse,
    GetPermissionResponse,
)
from .utils import authenticated, requires
from ..logger import make_logger
from ..schema import spec

blueprint = Blueprint("auth", __name__)

logger = make_logger("reachtalent.auth")


@blueprint.post("/login")
def login():
    """ Client and Candidate Login Endpoint.
    ---
    post:
      operationId: login
      tags:
        - auth
      requestBody:
        required: true
        content:
          application/json:
            schema: LoginRequest
      summary: Login with email and password.
      description: Use credentials to get an auth token
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: LoginResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data = {}
    try:
        data = LoginRequest().loads(request.data)
    except ValidationError as err:
        logger.debug(f"Invalid login request: `{request.data}` `{err.normalized_messages()}`")
        abort(400, err)

    users = db.session.execute(
        User.select_by_email(data['email'])
    ).scalars().all()

    if not users:
        logger.info(f"No user found for email `{data['email']}`")
        abort(400, "Invalid credentials")
    if len(users) > 1:
        # NB: Shouldn't happen unless user.email no longer has unique constraint in database
        logger.error(f"Multiple users found for email `{data['email']}`")
        abort(400, "Invalid credentials")
    user = users[0]

    if not user.check_password(data['password']):
        logger.info(f"Login password check failed for `{data['email']}`")
        abort(400, "Invalid credentials")

    if user.auth_provider_id != 1:
        user.auth_provider_id = 1
        db.session.add(user)
        db.session.commit()

    resp = Response(LoginResponse().dumps({}))
    resp.set_cookie("AuthToken",
                    tokens.make_auth_token(current_app, user),
                    secure=True, samesite="strict")
    return resp


@blueprint.post('/signup')
def signup():
    """ Candidate Sign Up Endpoint.
    ---
    post:
      operationId: signup
      tags:
        - auth
      requestBody:
        required: true
        content:
          application/json:
            schema: SignupRequest
      summary: Sign Up
      description: Register a new account with email, name and password.
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: SignupResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    default_response = Response(SignupResponse().dumps({}), status=202, mimetype='application/json')
    data = {}
    try:
        data = SignupRequest().loads(request.data)
    except ValidationError as err:
        logger.debug(f"Invalid signup request: `{request.data}` `{err.normalized_messages()}`")
        abort(400, err)

    users = db.session.execute(User.select_by_email(data['email'])).scalars().all()
    if len(users) > 1:
        # NB: Shouldn't happen unless user.email no longer has unique constraint in database
        logger.error(f"Multiple users found for email `{data['email']}`")
        return default_response
    elif users:
        logger.warning(f"Signup for existing email `{data['email']}`")
        email.notify_existing_user(current_app, users[0])
        return default_response

    try:
        user = User(email=data['email'], password=data['password'], name=data['name'])
        db.session.add(user)
        db.session.commit()
    except IntegrityError as exc:
        # Race-Condition edge case
        logger.warning(f"Integrity error when inserting User {data['email']}: {exc}")
        return default_response

    email.send_verify_email(current_app, user)

    return default_response


@blueprint.post('/email_verify')
def email_verify():
    """ Email Verification Endpoint.
    ---
    post:
      operationId: verifyEmail
      tags:
       - auth
      requestBody:
        required: true
        content:
          application/json:
            schema: EmailVerifyRequest
      summary: Verify Account Email
      description: Use the token from the verification email link to verify the user's email.
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: EmailVerifyResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    data = {}
    try:
        data = EmailVerifyRequest(app=current_app).loads(request.data)
    except ValidationError as err:
        logger.debug(f"Invalid email_verify request: `{request.data}` `{err.normalized_messages()}`")
        abort(400, err)

    payload = {}
    try:
        payload = tokens.decode(current_app, data['token'])
    except Exception as exc:
        logger.info(f"Exception decoding token: {exc}")
        abort(400, "Invalid request")

    use = payload.get('use')
    uid = payload.get('sub')
    rti = payload.get('rti', {})
    user_email = rti.get('email')

    if use != 'passreset' or not uid or not user_email:
        logger.warning(f"Received email verify with invalid payload: `{payload}`")
        abort(400, "Invalid request")

    users = db.session.execute(User.select_by_email(user_email)).scalars().all()

    if len(users) > 1:
        # NB: Shouldn't happen unless user.email no longer has unique constraint in database
        logger.error(f"Multiple users found for email `{user_email}`")
        abort(400, "Unable to verify email")
    elif not users:
        logger.error(f"No user found for email `{user_email}`")
        abort(400, "Unable to verify email")

    user = users[0]
    if user.id != uid:
        logger.error(f"User ID mismatch, token id `{uid}` does not match `{user.id}")
        abort(400, "Unable to verify email")

    if not user.email_verified:
        user.email_verified = True
        db.session.add(user)
        db.session.commit()

    return Response(EmailVerifyResponse().dumps({}), status=200, mimetype='application/json')


@blueprint.post('/forgot_password/send')
def send_forgot_password():
    """ Send Forgot Password
    ---
    post:
      operationId: sendForgotPassword
      tags:
       - auth
      requestBody:
        required: true
        content:
          application/json:
            schema: SendForgotPasswordRequest
      summary: Request to email a user with a link to reset their password
      description: Request to email a user with a link to reset their password
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: SendForgotPasswordResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data = {}
    try:
        data = SendForgotPasswordRequest().loads(request.data)
    except ValidationError as err:
        logger.debug("Invalid email_verify request: `%s` `%s`", request.data, err.normalized_messages())
        abort(400, err)

    try:
        user = User.query.filter_by(email=data['email']).one()
        email.send_forgot_password(current_app, user)
    except NoResultFound:
        logger.info("Send Forgot Password request from unknown email: `%s`", data['email'])

    return Response(SendForgotPasswordResponse().dumps({}), 202)


@blueprint.post('/forgot_password/reset')
def forgot_password_reset():
    """ Reset Password
    ---
    post:
      operationId: resetForgotPassword
      tags:
       - auth
      requestBody:
        required: true
        content:
          application/json:
            schema: ResetPasswordRequest
      summary: Reset Password
      description: Reset Password
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ResetPasswordResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data = {}
    try:
        data = ResetPasswordRequest(app=current_app).loads(request.data)
    except ValidationError as err:
        logger.debug("Invalid forgot_password_reset request: `%s` `%s`",
                     request.data, err.normalized_messages())
        abort(400, err)

    token = tokens.decode(current_app, data['token'])

    try:
        user = User.query.filter_by(email=token['rti']['email']).one()
        if user.id != token['sub']:
            logger.error("User ID mismatch, token id `%s` does not match `%s`",
                         token['sub'], user.id)
            abort(400, "Unable to reset password.")

        user.password = data['password']
        if not user.email_verified:
            user.email_verified = True
        db.session.add(user)
        db.session.commit()
    except (OrmNoResultFound, NoResultFound) as exc:
        logger.warning(
            "Forgot Password Reset user not found: token:`%s` exc:`%s`",
            token, exc)
        abort(400, "Unable to reset password.")

    return Response(ResetPasswordResponse().dumps({}))


@blueprint.post('/invite')
@authenticated
@requires("Client.*.create")
def send_invite(user: User):
    """ Send Invite Email
    ---
    post:
      operationId: sendInvite
      tags:
       - auth
      requestBody:
        required: true
        content:
          application/json:
            schema: SendInviteRequest
      summary: Request to email a user with a link to set their password
      description: >
        This endpoint is used when onboarding a new Client. After using the
        sync_client command, this endpoint will email a user a welcome message
        with a link to a page to set a password and verify their email. If the
        user has a password set and already verified their email address no
        message will be sent.
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: SendInviteResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data = {}
    email_sent = False
    try:
        data = SendInviteRequest().loads(request.data)
    except ValidationError as err:
        logger.debug("Invalid send_invite request: `%s` `%s`", request.data, err.normalized_messages())
        abort(400, err)
    except json.decoder.JSONDecodeError as err:
        logger.debug("Invalid json request: `%s` `%s`", request.data, err)
        abort(400, "Invalid request body.")

    try:
        user = db.session.query(User).filter_by(email=data['email']).one()
        if user.email_verified and user.password:
            # No need to send invite email
            pass
        elif user.password and not user.email_verified:
            # User exists and had set a password but never verified email
            email.send_verify_email(current_app, user)
            email_sent = True
        elif not user.password and not user.email_verified:
            # User likely created by import script, send welcome email with link to password reset
            email.send_verify_email(current_app, user, link_path='reset_password')
            email_sent = True
        else:
            # Should be impossible to have a user email verified but without a
            # password, just safeguard against shenanigans.
            abort(400, "Invalid request")
    except NoResultFound:
        logger.info("Send Invite request for unknown email: `%s`", data['email'])
        abort(404, "User not found.")

    return Response(
        SendInviteResponse().dumps({'invite_sent': email_sent}),
        200, content_type="application/json")


@blueprint.get('/permissions')
@authenticated
def get_permissions(user: User):
    """Get User's Permissions
    ---
    get:
      operationId: getPermissions
      tags:
       - auth
      summary: Get User's Permissions
      description: Get User's Permissions
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: GetPermissionResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    return Response(
        GetPermissionResponse().dumps({
            'role': g.auth_state.role.name,
            'permissions': sorted(
                g.auth_state.role.permissions,
                key=lambda p: p.name,
            ),
        }),
        content_type="application/json")


@blueprint.post('/session')
@authenticated
def update_session(user: User):
    """Refresh JWT Session
    ---
    post:
      operationId: updateSession
      tags:
       - auth
      requestBody:
        required: false
        content:
          application/json:
            schema: AuthSessionRequest
      summary: Refresh JWT Session and Optional switch active client
      description: Refresh JWT Session and Optional switch active client
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: AuthSessionResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data = {}
    raw_data = request.data
    if raw_data:
        try:
            data = AuthSessionRequest(auth_state=g.auth_state).loads(request.data)
        except ValidationError as err:
            logger.debug("Invalid update_session request: `%s` `%s`",
                         request.data, err.normalized_messages())
            abort(400, err)

    resp = Response(
        AuthSessionResponse().dumps({}),
        content_type="application/json")

    resp.set_cookie(
        "AuthToken",
        tokens.make_auth_token(current_app, user, client_id=data.get('client_id')),
        secure=True, samesite="strict")

    return resp


google_bp = make_google_blueprint(
    scope=[
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid",
    ],
    storage=NullStorage(),
)
blueprint.register_blueprint(google_bp)

linkedin_bp = make_linkedin_blueprint(
    scope="r_emailaddress,r_liteprofile",
)
blueprint.register_blueprint(linkedin_bp)

facebook_bp = make_facebook_blueprint(
    scope=["public_profile", "email"],
)
blueprint.register_blueprint(facebook_bp)


class AppleOauth2Session(OAuth2Session):

    def authorization_url(self, url, state=None, **kwargs):
        _url, state = super().authorization_url(url, state=state, **kwargs)
        # Replace plus encoding with percent encoding for scope as Apple requires.
        _url = _url.replace('scope=name+email', 'scope=name%20email')
        logger.info('_url: %s', _url)
        return _url, state

    def fetch_token(self, *args, **kwargs):
        # Pass client_id to session, so it could trigger Basic Auth
        logger.info("apple_oauth2_session.fetch_token(%s, %s)", args, kwargs)
        return super().fetch_token(
            include_client_id=True,
            method="POST",
            code=request.form.get("code"),
            *args,
            **kwargs,
        )


apple_bp = OAuth2ConsumerBlueprint(
    "apple",
    __name__,
    scope=['name', 'email'],
    base_url="https://appleid.apple.com/",
    token_url="https://appleid.apple.com/auth/token",
    authorization_url="https://appleid.apple.com/auth/authorize",
    authorization_url_params={'response_mode': 'form_post'},
    session_class=AppleOauth2Session,
    rule_kwargs={'methods': ['GET', 'POST']}
)
apple_bp.from_config["client_id"] = "APPLE_OAUTH_CLIENT_ID"
# TODO: Generate short-lived client_secret at service startup from private key
apple_bp.from_config["client_secret"] = "APPLE_OAUTH_CLIENT_SECRET"
blueprint.register_blueprint(apple_bp)

AUTH_PROVIDERS = {
    1: "Local",
    2: "Google",
    3: "LinkedIn",
    4: "Apple",
    5: "Facebook",
}


def flash(msg, **kwargs):
    logger.debug(f"{msg}: {kwargs}")


def validate_required_parameters(**kwargs) -> ValidationError:
    resp = None
    errors = {}
    for arg, value in kwargs.items():
        if not value:
            errors[arg] = ["Parameter is required"]
    if errors:
        resp = ValidationError(errors, None)
    return resp


def oauth_login(provider_id, ext_ref, user_email, email_verified, name, data) -> Response:
    """
    Generic sign-up/login handler for oauth authorized flows.
    """
    if validation_error := validate_required_parameters(provider_id=provider_id, ext_ref=ext_ref,
                                                        user_email=user_email):
        raise validation_error

    # Find Existing User or Create new one
    query = UserProfile.query.filter_by(
        auth_provider_id=provider_id, ext_ref=ext_ref)
    try:
        oauth = query.one()
        user = oauth.user
    except NoResultFound:
        try:
            user = User.query.filter_by(email=user_email).one()
        except NoResultFound:
            user = User(
                name=name,
                email=user_email,
                email_verified=email_verified,
                auth_provider_id=provider_id,
            )
            db.session.add(user)
            db.session.flush()

        oauth = UserProfile(
            auth_provider_id=provider_id,
            user_id=user.id,
            ext_ref=ext_ref,
            json_data=data,
        )
        db.session.add(oauth)

    # If google email is verified and matches the user email, mark the email
    # as verified.
    if email_verified and not user.email_verified:
        user.email_verified = True
        db.session.add(user)

    if user.auth_provider_id != provider_id:
        user.auth_provider_id = provider_id
        db.session.add(user)

    db.session.commit()
    resp = redirect("/", code=302)
    resp.set_cookie(
        "AuthToken", tokens.make_auth_token(current_app, user),
        secure=True, samesite="strict")

    return resp


@oauth_authorized.connect_via(google_bp)
def google_logged_in(bp, token):
    provider = AuthProvider.query.filter(
        func.lower(AuthProvider.name) == func.lower(bp.name)).one()
    logger.debug(f"Got token: {token}")
    if not token:
        flash("Failed to log in.", category="error")
        return False

    # use requests-oauthlib Session to retrieve user profile
    resp = bp.session.get("/oauth2/v1/userinfo")
    if not resp.ok:
        flash("Failed to fetch user info.", category="error")
        return False

    info = resp.json()

    return oauth_login(provider.id, info['id'], info['email'], info['verified_email'], info['name'], info)


@oauth_authorized.connect_via(linkedin_bp)
def linkedin_logged_in(bp, token):
    provider = AuthProvider.query.filter(
        func.lower(AuthProvider.name) == func.lower(bp.name)).one()
    logger.debug(f"Got token: {token}")
    if not token:
        flash("Failed to log in.", category="error")
        return False

    # use requests-oauthlib Session to retrieve user profile
    me_resp = bp.session.get("me")

    if not me_resp.ok:
        logger.warning(f"Failed to fetch /linkedin/v2/me [{me_resp.status_code}]: {me_resp.content}")
        msg = "Failed to fetch user info."
        flash(msg, category="error")
        return False

    info = me_resp.json()
    logger.debug("/linkedin/v2/me response: %s", info)

    email_resp = bp.session.get("emailAddress?q=members&projection=(elements*(handle~))")

    if not email_resp.ok:
        logger.warning(
            "Failed to fetch /linkedin/v2/emailAddress [%s]: %s",
            email_resp.status_code, email_resp.content)
        msg = "Failed to fetch user info."
        flash(msg, category="error")
        return False

    email_info = email_resp.json()
    logger.debug("/linkedin/v2/emailAddress response: %s", email_info)

    data = {
        'me': info,
        'emailAddress': email_info,
    }
    return oauth_login(
        provider.id,
        info['id'],
        email_info['elements'][0]['handle~']['emailAddress'],
        True,  # LinkedIn primary email is always verified.
        f"{info['localizedFirstName']} {info['localizedLastName']}",
        data)


@oauth_authorized.connect_via(facebook_bp)
def facebook_logged_in(bp, token):
    provider = AuthProvider.query.filter(
        func.lower(AuthProvider.name) == func.lower(bp.name)).one()
    logger.debug(f"Got token: {token}")
    if not token:
        flash("Failed to log in.", category="error")
        return False

    # use requests-oauthlib Session to retrieve user profile
    me_resp = bp.session.get("/me?fields=id,name,email")

    if not me_resp.ok:
        logger.warning(
            "Failed to fetch /facebook/me [%s]: %s",
            me_resp.status_code, me_resp.content)
        msg = "Failed to fetch user info."
        flash(msg, category="error")
        return False

    info = me_resp.json()
    logger.debug("/facebook/me response: %s", info)

    return oauth_login(
        provider.id,
        info['id'],
        info['email'],
        True,  # Facebook Primary email is always verified.
        info['name'],
        info)


def construct_name(user_info: dict, id_payload: dict) -> str:
    name = 'Unknown Name'
    if 'name' in user_info:
        name = user_info['name']['firstName'] + ' ' + user_info['name']['lastName']
    elif 'email' in id_payload and '@' in id_payload['email']:
        email_part = id_payload['email'].split('@')[0].title()
        if email_part:
            name = email_part
    return name


def is_email_verified(id_payload: dict) -> bool:
    verified = id_payload.get('email_verified')
    if verified:
        if isinstance(verified, str):
            return verified == 'true'
        if isinstance(verified, bool):
            return verified
    return False


@oauth_authorized.connect_via(apple_bp)
def apple_logged_in(bp, token):
    provider = AuthProvider.query.filter(
        func.lower(AuthProvider.name) == func.lower(bp.name)).one()
    logger.debug(f"Got token: {token}")
    id_token = (token or {}).get('id_token', '')
    if not id_token:
        flash("Failed to log in.", category="error")
        return False

    # Apple Sends User info in form-post response
    user_info = json.loads(request.form.get('user', '{}'))

    id_payload = jwt.decode(id_token, options={"verify_signature": False})

    name = construct_name(user_info, id_payload)

    return oauth_login(
        provider.id,
        id_payload['sub'],
        id_payload['email'],
        is_email_verified(id_payload),
        name,
        {
            'user': user_info,
            'id_payload': id_payload
        })


# notify on OAuth provider error
@oauth_error.connect_via(google_bp)
def google_error(bp, message, response):
    flash(f"OAuth error from {bp.name}! "
          f"message={message} response={response}", category="error")


# Register blueprint commands
blueprint.cli.add_command(commands.sync_data, 'sync_data')


def init(app: Flask):
    with app.app_context():
        spec.path(view=login)
        spec.path(view=signup)
        spec.path(view=email_verify)
        spec.path(view=send_invite)
        spec.path(view=send_forgot_password)
        spec.path(view=forgot_password_reset)
        spec.path(view=get_permissions)
        spec.path(view=update_session)
