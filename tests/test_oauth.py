from urllib.parse import urlparse, parse_qs

from flask import session

from reachtalent.database import db

from reachtalent.auth.models import User

from .conftest import assert_login_as


def test_google_auth(client, app, requests_mock):
    with client:
        login_resp = client.get('/api/auth/google')

        assert login_resp.status_code == 302
        assert login_resp.location

        google_auth_url = urlparse(login_resp.location)

        # Assert google auth url
        assert google_auth_url[:3] == ('https', 'accounts.google.com', '/o/oauth2/auth')

        state = session['google_oauth_state']

        assert parse_qs(google_auth_url.query) == {
            'response_type': ['code'],
            'scope': [
                'https://www.googleapis.com/auth/userinfo.email '
                'https://www.googleapis.com/auth/userinfo.profile '
                'openid'
            ],
            'redirect_uri': ['https://reachtalent.com/api/auth/google/authorized'],
            'client_id': ['_google_client_id'],
            'state': [state],
        }

        """
        POST /token HTTP/1.1
        Host: oauth2.googleapis.com
        Content-Type: application/x-www-form-urlencoded
        
        code=4/P7q7W91a-oMsCeLvIaQm6bTrgtp7&
        client_id=your_client_id&
        client_secret=your_client_secret&
        redirect_uri=https%3A//oauth2.example.com/code&
        grant_type=authorization_code
        """
        # TODO: Assert params
        requests_mock.post(
            "https://accounts.google.com/o/oauth2/token",
            json={
                "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
                "expires_in": 3920,
                "token_type": "Bearer",
                "scope":
                    'https://www.googleapis.com/auth/userinfo.email '
                    'https://www.googleapis.com/auth/userinfo.profile '
                    'openid',
                "refresh_token": "1//xEoDL4iW3cxlI7yDbSRFYNG01kVKM2C-259HOF2aQbI"
            },
        )
        userinfo_payload = {
            "id": "106289769395363482359",
            "email": "mario@example.com",
            "verified_email": True,
            "name": "Mario Ario",
            "given_name": "Mario",
            "family_name": "Ario",
            "picture": "https://lh3.googleusercontent.com/a/AEdFTp5YYHNNNMy_H_pAnL-BxZc7ZQF1pF6cPMv9nRVe=s96-c",
            "locale": "en",
            "hd": "example.com",
        }
        requests_mock.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            json=userinfo_payload,
        )
        fake_auth_code = "fake-auth-code"
        authorized_resp = client.get(f'/api/auth/google/authorized?state={state}&code={fake_auth_code}')

        assert authorized_resp.status_code == 302
        assert authorized_resp.location == '/'

        assert_login_as(
            authorized_resp, 'mario@example.com',
            user_id=1, email_verified=True, name='Mario Mario')

        with app.app_context():
            user = db.session.get(User, 1)
            assert user.auth_provider_id == 2


def test_linkedin_auth(client, app, requests_mock):
    with client:
        login_resp = client.get('/api/auth/linkedin')

        assert login_resp.status_code == 302
        assert login_resp.location

        linkedin_auth_url = urlparse(login_resp.location)

        # Assert google auth url
        assert linkedin_auth_url[:3] == ('https', 'www.linkedin.com', '/oauth/v2/authorization')

        state = session['linkedin_oauth_state']

        assert parse_qs(linkedin_auth_url.query) == {
            'response_type': ['code'],
            'scope': ['r_emailaddress,r_liteprofile'],
            'redirect_uri': ['https://reachtalent.com/api/auth/linkedin/authorized'],
            'client_id': ['_linkedin_client_id'],
            'state': [state],
        }

        requests_mock.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            json={
                "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
                "expires_in": 3920,
                "token_type": "Bearer",
                "scope": 'r_emailaddress,r_liteprofile',
                "refresh_token": "1//xEoDL4iW3cxlI7yDbSRFYNG01kVKM2C-259HOF2aQbI"
            },
        )

        userinfo_payload = {
            "id": "linkedin.joe.smith",
            "localizedLastName": "Joe",
            "localizedFirstName": "Smith",
            "profilePicture": {"displayImage": "urn:li:digitalmediaAsset:ZXcfeaeio123-zxfdr3"},
            "firstName": {"localized": {"en_US": "Joe"}, "preferredLocale": {"country": "US", "language": "en"}},
            "lastName": {"localized": {"en_US": "Smith"}, "preferredLocale": {"country": "US", "language": "en"}},
        }

        requests_mock.get(
            "https://api.linkedin.com/v2/me",
            json=userinfo_payload,
        )
        email_payload = {"elements": [
            {"handle~": {"emailAddress": "joe@example.com"}, "handle": "urn:li:emailAddress:12341234"}]}
        requests_mock.get(
            "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
            json=email_payload,
        )

        fake_auth_code = "fake-auth-code"
        authorized_resp = client.get(f'/api/auth/linkedin/authorized?state={state}&code={fake_auth_code}')

        assert authorized_resp.status_code == 302
        assert authorized_resp.location == '/'

        assert_login_as(
            authorized_resp, 'joe@example.com',
            user_id=2, email_verified=True, name='Joe Smith')

        with app.app_context():
            user = db.session.get(User, 2)
            assert user.auth_provider_id == 3


def test_facebook_auth(client, app, requests_mock):
    with client:
        login_resp = client.get('/api/auth/facebook')

        assert login_resp.status_code == 302
        assert login_resp.location

        linkedin_auth_url = urlparse(login_resp.location)

        # Assert google auth url
        assert linkedin_auth_url[:3] == ('https', 'www.facebook.com', '/dialog/oauth')

        state = session['facebook_oauth_state']

        assert parse_qs(linkedin_auth_url.query) == {
            'response_type': ['code'],
            'scope': ['public_profile email'],
            'redirect_uri': ['https://reachtalent.com/api/auth/facebook/authorized'],
            'client_id': ['_facebook_client_id'],
            'state': [state],
        }

        requests_mock.post(
            "https://graph.facebook.com/oauth/access_token",
            json={
                "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
                "expires_in": 3920,
                "token_type": "Bearer",
                "scope": 'public_profile email',
                "refresh_token": "1//xEoDL4iW3cxlI7yDbSRFYNG01kVKM2C-259HOF2aQbI"
            },
        )

        userinfo_payload = {
            "id": "facebook.joe.smith",
            "name": "Joe Smith",
            "email": "joe@example.com",
        }

        requests_mock.get(
            "https://graph.facebook.com/me",
            json=userinfo_payload,
        )

        fake_auth_code = "fake-auth-code"
        authorized_resp = client.get(f'/api/auth/facebook/authorized?state={state}&code={fake_auth_code}')

        assert authorized_resp.status_code == 302
        assert authorized_resp.location == '/'

        assert_login_as(
            authorized_resp, 'joe@example.com',
            user_id=2, email_verified=True, name='Joe Smith')

        with app.app_context():
            user = db.session.get(User, 2)
            assert user.auth_provider_id == 5


def test_apple_auth(client, app, requests_mock):
    with client:
        login_resp = client.get('/api/auth/apple')

        assert login_resp.status_code == 302
        assert login_resp.location

        linkedin_auth_url = urlparse(login_resp.location)

        # Assert google auth url
        assert linkedin_auth_url[:3] == ('https', 'appleid.apple.com', '/auth/authorize')

        state = session['apple_oauth_state']

        assert parse_qs(linkedin_auth_url.query) == {
            'response_type': ['code'],
            'scope':  ['name email'],
            'redirect_uri': ['https://reachtalent.com/api/auth/apple/authorized'],
            'response_mode': ['form_post'],
            'client_id': ['_apple_client_id'],
            'state': [state],
        }

        requests_mock.post(
            "https://appleid.apple.com/auth/token",
            json={
                "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
                "expires_in": 3920,
                "token_type": "Bearer",
                "scope": 'name email',
                "refresh_token": "1//xEoDL4iW3cxlI7yDbSRFYNG01kVKM2C-259HOF2aQbI",
                "id_token": "eyJraWQiOiJmaDZCczhDIiwiYWxnIjoiUlMyNTYifQ.eyJpc3MiOiJodHRwczovL2FwcGxlaWQuYXBwbGUuY29tIiwiYXVkIjoiY29tLnJvYmVydHJhbXNheS5yZWFjaHRhbGVudC1hdXRoIiwiZXhwIjoxNjc2NjU2MzA0LCJpYXQiOjE2NzY1Njk5MDQsInN1YiI6IjAwMTEwMy45MWE1MzZkN2VhY2I0M2IwOTZkZDA0ZTNmZmJlMjcwOS4wMDU2IiwiYXRfaGFzaCI6IlFRb3I2U2ZIaVNpX3JTbnZHLVdpSmciLCJlbWFpbCI6InJhbXNheUByZWFjaHRhbGVudC5jb20iLCJlbWFpbF92ZXJpZmllZCI6InRydWUiLCJhdXRoX3RpbWUiOjE2NzY1Njk5MDMsIm5vbmNlX3N1cHBvcnRlZCI6dHJ1ZX0.oKuqIAAxy6Y57JvKqr82i2TTx0U70wdFQT3wNk_sNe-IPa42emnUnntp2CD_QtUYJkVn0LVUKldzXOIveYy70if1vyb6W9ReLCV0G2i-7CQuv5WZlzMtBOWCf4ErFSx1W855oFqvQwUjcZ2Us1rrbM4wLF9ypoTJ_eE1Pn_ksCpxGOM9oafuDzFbv4ubGkmVMVLkvwWgFgK6t2F2Xg1e0mFmGAOSREf9EMCsvL_lzzDx1BkwxaBXWnBAfu7q7XZpZzx-MWKCEzN2avgZCOzJCV21YYxEzZu9Tac4kASF4YszmM0pQXCrhuApIHQN-EdJ4BmlmW-hpHvvrACZnqqLsw",
            },
        )

        fake_auth_code = "fake-auth-code"
        authorized_resp = client.post(f'/api/auth/apple/authorized', data={
            'state': state,
            'code': fake_auth_code,
            'user': '{"name": {"firstName": "Robert", "lastName": "Ramsay"}, "email": "ramsay@reachtalent.com"}'
        })

        assert authorized_resp.status_code == 302
        assert authorized_resp.location == '/'

        with app.app_context():
            user = User.query.filter_by(email='ramsay@reachtalent.com').one()

            assert_login_as(
                authorized_resp,
                'ramsay@reachtalent.com',
                user_id=user.id,
                email_verified=True,
                name='Robert Ramsay')

            assert user.auth_provider_id == 4
