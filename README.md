# 🤖 Kimi AI Question Generator

A secure web interface to ask Kimi K2.5 AI questions, now with user authentication!

## Features

- 🎨 Beautiful, responsive web interface
- 🚀 One-click to ask Kimi questions
- ✏️ Customizable questions (or use pre-defined)
- ⚡ Real-time loading indicator
- 📱 Works on desktop and mobile
- 🔐 **User authentication system** - secure login/logout
- 🛡️ Password hashing for security
- 👤 Multi-user support (optional registration)

## What's New - Authentication System

The app now includes a complete user authentication system:

- **Login required** to access the main page
- **Password hashing** with Werkzeug (secure)
- **Session management** with Flask-Login
- **User registration** (can be disabled in production)
- **SQLite database** for user storage

Default credentials (auto-created on first run):
- Username: `admin`
- Password: `kimi2024`

⚠️ **Important**: Change the default password after first login!

## Installation

1. Install dependencies:
```bash
pip3 install -r requirements.txt
```

2. Run the app:
```bash
python3 app.py
```

3. Open browser and go to:
```
http://localhost:5000
```

4. Login with default credentials:
   - Username: `admin`
   - Password: `kimi2024`

5. (Optional) Create your own account via the Register page

## File Structure

```
kimi_webapp/
├── app.py                 # Main Flask application with auth
├── requirements.txt       # Python dependencies
├── templates/
│   ├── index.html        # Main app page (protected)
│   ├── login.html        # Login page
│   └── register.html     # Registration page
└── users.db              # SQLite database (auto-created)
```

## Configuration

### Environment Variables (Recommended for Production)

Set these environment variables for better security:

```bash
export SECRET_KEY='your-random-secret-key-here'
export KIMI_API_KEY='your-kimi-api-key'
```

### Disabling Registration

To disable user registration in production, comment out or remove the `/register` route in `app.py`:

```python
# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     ...
```

## Security Features

1. **Password Hashing**: All passwords are hashed with Werkzeug's `generate_password_hash`
2. **Session Management**: Flask-Login handles secure user sessions
3. **CSRF Protection**: Secret key required for session security
4. **Input Validation**: Username/password validation on registration
5. **Protected Routes**: Main page and API require authentication

## Usage

### For Admin/Owner

1. Login with `admin` / `kimi2024`
2. Change the default password (recommended)
3. Optionally disable registration after creating accounts
4. Deploy with environment variables set

### For Users

1. Register an account (if enabled) or use provided credentials
2. Login with your username and password
3. Enter your question in the text box
4. Click "Ask Kimi" and wait for the AI response
5. Click "Logout" when finished

## Keyboard Shortcuts

- **Ctrl+Enter** (or Cmd+Enter on Mac): Submit question

## Deployment Notes

### Before Deploying to Production:

1. ✅ Change default `admin` password
2. ✅ Set strong `SECRET_KEY` environment variable
3. ✅ Set `KIMI_API_KEY` environment variable (remove from code)
4. ✅ Consider disabling registration
5. ✅ Use HTTPS (required for secure cookies)
6. ✅ Set `debug=False` in production

### Recommended Platforms

- **Render**: Easy Python deployment with environment variables
- **PythonAnywhere**: Good for Flask apps, free tier available
- **Railway**: Modern platform with automatic deployments

## Troubleshooting

### Database Issues

If you get database errors, delete `users.db` and restart - it will auto-recreate with the default user.

### Login Issues

- Make sure cookies are enabled in your browser
- Clear browser cache if experiencing issues
- Check that `SECRET_KEY` is set consistently

## API Configuration

The API key is loaded from environment variable `KIMI_API_KEY`. If not set, it falls back to the default in the code (not recommended for production).

---

Built with ❤️ using Flask + Kimi K2.5 + Flask-Login
