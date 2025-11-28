from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from models import User
from extensions import limiter

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config['LOGIN_RATE_LIMIT'])
def login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin.dashboard'))

        flash('用户名或密码错误')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    """退出登录"""
    logout_user()
    return redirect(url_for('public.index'))