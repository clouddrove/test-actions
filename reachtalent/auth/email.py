from flask import Flask, render_template
from flask_mail import Message

from ..extensions import mail
from .models import User
from . import tokens


send_verify_email_tmpl = """
Dear {user.name},

We are thrilled to welcome you to Reach Talent, the leading platform connecting 
talented professionals with the best job opportunities. To ensure the security 
of your account, we require all new users to verify their email address.

Please click on the link below to confirm your email and complete your registration:

https://{host}/{link_path}?token={token}

By verifying your email address, you will have full access to our platform, where 
you can browse job listings, apply for positions, and connect with recruiters 
and hiring managers.

At Reach Talent, we are committed to providing our users with the best 
experience possible. If you have any questions or concerns, please don't 
hesitate to contact our customer support team at support@reachtalent.com.

Thank you for joining Reach Talent, and we look forward to helping you achieve 
your career goals.

Best regards,

Reach Talent Team
"""


def send_verify_email(app: Flask, user: User, link_path: str = 'verify_email'):
    tmpl_context = {
        'user': user,
        'host': app.config.get('SERVER_NAME'),
        'link_path': link_path,
        'token': tokens.make_email_verify_token(app, user)
    }
    msg = Message(
        "Welcome to Reach Talent",
        recipients=[user.email],
        body=send_verify_email_tmpl.format(**tmpl_context),
        html=render_template("send_verify_email.html", **tmpl_context),
    )
    mail.send(msg)


notify_existing_user_tmpl = """
Dear {user.name},

We are reaching out to notify you that someone recently attempted to sign up for 
an account on Reach Talent using your email address. If you did not initiate 
this sign-up, you can safely ignore this message.

However, if you did initiate the sign-up process and have forgotten your 
password, you can reset it by following this link: 

https://{host}/forgot_password 

This will allow you to create a new password and access your account.

If you did not attempt to sign up for Reach Talent, your email may have been 
entered by mistake. No action is needed on your part and your information 
remains secure. If you have any concerns or questions, please contact us at 
support@reachtalent.com.

Thank you for your attention to this matter.

Best regards,
The Reach Talent Team
"""


def notify_existing_user(app: Flask, user: User):
    tmpl_context = {
        'user': user,
        'host': app.config.get('SERVER_NAME'),
    }
    msg = Message(
        "Attempted Sign-up to Reach Talent",
        recipients=[user.email],
        body=notify_existing_user_tmpl.format(**tmpl_context),
        html=render_template("notify_existing_user.html", **tmpl_context)
    )
    mail.send(msg)


forgot_password_tmpl = """
Dear {user.name},

We have received your request to reset your password for the Reach Talent 
System. Please click on the link below to reset your password:

https://{host}/reset_password?token={token}

This link will expire in 24 hours, so please make sure to reset your password 
as soon as possible. If the link has expired, you can request a new one by 
following the password reset process again.

Please note that for security purposes, we do not store passwords in our 
system. As a result, we cannot retrieve your old password. If you have any 
questions or concerns, please contact our customer support team at 
support@reachtalent.com.

Best regards, 
The Reach Talent Team
"""


def send_forgot_password(app: Flask, user: User):
    tmpl_context = {
        'user': user,
        'token': tokens.make_email_verify_token(app, user),
        'host': app.config.get('SERVER_NAME'),
    }
    msg = Message(
        "Password Reset for Reach Talent System",
        recipients=[user.email],
        body=forgot_password_tmpl.format(**tmpl_context),
        html=render_template("send_forgot_password.html", **tmpl_context)
    )
    mail.send(msg)
