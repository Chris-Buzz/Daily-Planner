# 📅 Planno - Daily Planning Assistant# 📅 Daily Planner - Intelligent Task Management App



A modern, feature-rich daily planner application built with Flask and vanilla JavaScript. Planno helps you organize your tasks, manage your schedule, and stay productive across all your devices.A powerful, AI-driven daily planner with smart notifications, weather integration, and comprehensive task management capabilities.



![Planno Banner](static/PlannerIcon.png)![Daily Planner](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)

![Flask](https://img.shields.io/badge/Flask-2.3.3-blue)

## ✨ Features![Firebase](https://img.shields.io/badge/Firebase-Admin%206.2.0-orange)

![PWA](https://img.shields.io/badge/PWA-Ready-purple)

### 📝 Task Management

- **Create, edit, and delete tasks** with ease## ✨ Features

- **Multi-day task creation** - Add tasks to multiple days or all days at once

- **Priority levels** (Low, Medium, High) with color coding### 🎯 **Core Task Management**

- **Time-based scheduling** with start and end times- **Smart Task Creation**: Intuitive forms with time ranges, priorities, and categories

- **Custom color coding** for better task organization- **Weekly/Daily Views**: Seamless navigation between different time periods

- **Drag and drop** tasks to reorder (desktop)- **Drag & Drop**: Reorganize tasks effortlessly

- **Bulk operations** - Delete all tasks for a day- **Task Categories**: Color-coded organization system

- **Completion Tracking**: Mark tasks complete with visual feedback

### 📆 Calendar & Scheduling

- **Week view calendar** with time slots### 🤖 **AI-Powered Assistant**

- **Visual task blocks** showing duration and timing- **Google Gemini Integration**: Intelligent task suggestions and planning

- **Navigate weeks** forward and backward- **Conversational Interface**: Natural language task creation

- **Class schedule generator** for students- **Smart Recommendations**: AI analyzes patterns and suggests optimal scheduling

- **Break time management** between classes- **Automated Task Creation**: Generate comprehensive schedules from simple requests

- **Recurring task support** across multiple days

### 🔔 **Smart Notifications**

### 🌤️ Weather Integration- **Multi-Channel Alerts**: Email and SMS notifications

- **Real-time weather** display for your location- **Intelligent Timing**: Automatic reminders based on task priority

- **7-day forecast** in calendar view- **Daily Summaries**: End-of-day progress reports

- **Weather-based suggestions** for task planning- **Spam Protection**: Advanced deduplication prevents notification overload

- **City search** for weather in different locations

- **OpenWeatherMap API** integration### 🌤️ **Weather Integration**

- **OpenWeatherMap API**: Real-time weather data

### 🔔 Smart Notifications- **Location-Based**: Automatic weather for your area

- **Email notifications** via SMTP (Gmail supported)- **7-Day Forecasts**: Plan ahead with weather-aware scheduling

- **SMS notifications** via Twilio- **Smart Suggestions**: AI considers weather when suggesting outdoor activities

- **Customizable reminder times** (15min, 30min, 1hr, 1 day before)

- **Daily summary emails** at your preferred time### 📱 **Progressive Web App (PWA)**

- **Task deadline alerts**- **Mobile Optimized**: Native app experience on mobile devices

- **Offline Capable**: Works without internet connection

### 🤖 AI Assistant- **Dark/Light Themes**: Persistent theme preferences

- **Google Gemini AI** integration- **Responsive Design**: Beautiful on all screen sizes

- **Intelligent task suggestions** based on your schedule

- **Natural language task creation**### 🔐 **Enterprise-Grade Security**

- **Schedule optimization** recommendations- **Firebase Authentication**: Secure user management

- **Weather-aware planning**- **Data Encryption**: All data encrypted in transit and at rest

- **HTTPS Enforcement**: Secure connections in production

### 🎨 User Experience- **Session Management**: Secure cookie-based sessions

- **Dark/Light theme** toggle

- **Fully responsive** - works on desktop, tablet, and mobile## 🚀 Quick Start

- **Mobile-optimized layout** with FAB (Floating Action Button)

- **Smooth animations** and transitions### Prerequisites

- **Accessible design** with ARIA labels- Python 3.8 or higher

- **Touch-friendly** interface for mobile devices- Firebase project with Firestore enabled

- Gmail account for email notifications (optional)

### 🔐 Security & Authentication- Twilio account for SMS notifications (optional)

- **Firebase Authentication** (Google Sign-In, Email/Password)- OpenWeatherMap API key (optional)

- **Remember Me** functionality- Google Gemini API key (optional)

- **Secure session management**

- **User data isolation** with Firestore### Installation

- **Privacy policy** page

1. **Clone the repository**

## 🚀 Live Demo   ```bash

   git clone <repository-url>

Visit the live application: **[https://planno-eta.vercel.app/](https://planno-eta.vercel.app/)**   cd daily-planner

   ```

## 🛠️ Tech Stack

2. **Install dependencies**

### Backend   ```bash

- **Flask** - Python web framework   pip install -r requirements.txt

- **Firebase Admin SDK** - Authentication and Firestore database   ```

- **Google Gemini AI** - AI-powered assistant

- **Twilio** - SMS notifications3. **Environment Setup**

- **SMTP** - Email notifications   Create a `.env` file in the root directory:

- **OpenWeatherMap API** - Weather data   ```env

   # Required

### Frontend   SECRET_KEY=your-secret-key-here

- **Vanilla JavaScript** - No frameworks, just pure JS   FLASK_ENV=development

- **HTML5 & CSS3** - Modern web standards   

- **CSS Grid & Flexbox** - Responsive layouts   # Firebase (Required)

- **CSS Variables** - Dynamic theming   FIREBASE_CREDENTIALS_PATH=path/to/firebase-credentials.json

   # OR for production (base64 encoded credentials)

### Deployment   FIREBASE_CREDENTIALS_BASE64=your-base64-encoded-credentials

- **Vercel** - Serverless deployment   

- **Firebase Firestore** - Cloud database   # Email Notifications (Optional)

- **Environment Variables** - Secure configuration   SMTP_SERVER=smtp.gmail.com

   SMTP_PORT=587

## 📦 Installation   SMTP_USERNAME=your-email@gmail.com

   SMTP_PASSWORD=your-app-password

### Prerequisites   

- Python 3.8+   # SMS Notifications (Optional)

- Firebase project   TWILIO_ACCOUNT_SID=your-twilio-sid

- Google Cloud account (for Gemini AI)   TWILIO_AUTH_TOKEN=your-twilio-token

- Twilio account (optional, for SMS)   TWILIO_PHONE_NUMBER=your-twilio-number

- Gmail account (optional, for email notifications)   

   # Weather Integration (Optional)

### 1. Clone the Repository   OPENWEATHERMAP_API_KEY=your-weather-api-key

```bash   

git clone https://github.com/Chris-Buzz/Daily-Planner.git   # AI Assistant (Optional)

cd Daily-Planner   GEMINI_API_KEY=your-gemini-api-key

```   ```



### 2. Install Dependencies4. **Firebase Setup**

```bash   - Create a Firebase project at [Firebase Console](https://console.firebase.google.com)

pip install -r requirements.txt   - Enable Firestore Database

```   - Enable Authentication (Email/Password)

   - Download service account credentials JSON file

### 3. Set Up Firebase   - Place the file in your project root or set `FIREBASE_CREDENTIALS_PATH`

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)

2. Enable Authentication (Google and Email/Password providers)5. **Run the application**

3. Create a Firestore database   ```bash

4. Download your service account JSON file   python planner.py

5. Place it in the project root as `daily-planner-57801-firebase-adminsdk-fbsvc-4751fc80f5.json`   ```



### 4. Configure Environment Variables6. **Access the app**

   Open your browser to `http://127.0.0.1:5000`

Create a `.env` file in the project root:

## 🔧 Configuration

```env

# Firebase Admin SDK### Firebase Setup

FIREBASE_TYPE=service_account1. Go to [Firebase Console](https://console.firebase.google.com)

FIREBASE_PROJECT_ID=your-project-id2. Create a new project or select existing

FIREBASE_PRIVATE_KEY_ID=your-private-key-id3. Enable Firestore Database

FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"4. Enable Authentication → Email/Password

FIREBASE_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com5. Go to Project Settings → Service Accounts

FIREBASE_CLIENT_ID=your-client-id6. Generate new private key and download JSON file

FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth

FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token### Email Configuration

FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certsFor Gmail SMTP:

FIREBASE_CLIENT_X509_CERT_URL=your-cert-url1. Enable 2-Factor Authentication

2. Generate App Password (not your regular password)

# Firebase Client (Frontend)3. Use App Password in `SMTP_PASSWORD`

FIREBASE_API_KEY=your-api-key

FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com### API Keys

FIREBASE_STORAGE_BUCKET=your-project.appspot.com- **OpenWeatherMap**: [Get free API key](https://openweathermap.org/api)

FIREBASE_MESSAGING_SENDER_ID=your-sender-id- **Google Gemini**: [Get API key](https://makersuite.google.com/app/apikey)

FIREBASE_APP_ID=your-app-id- **Twilio**: [Sign up for SMS service](https://www.twilio.com)

FIREBASE_MEASUREMENT_ID=your-measurement-id

## 🏗️ Architecture

# Flask Secret Key

SECRET_KEY=your-super-secret-key-here```

daily-planner/

# Email Configuration (Optional)├── planner.py              # Main Flask application

SMTP_SERVER=smtp.gmail.com├── static/

SMTP_PORT=587│   ├── script.js          # Frontend JavaScript

SMTP_USERNAME=your-email@gmail.com│   ├── styles.css         # Main styles

SMTP_PASSWORD=your-app-password│   ├── login.css          # Authentication styles

│   └── manifest.json      # PWA configuration

# Twilio Configuration (Optional)├── templates/

TWILIO_ACCOUNT_SID=your-account-sid│   ├── index.html         # Main application

TWILIO_AUTH_TOKEN=your-auth-token│   ├── login.html         # Login page

TWILIO_PHONE_NUMBER=+1234567890│   └── register.html      # Registration page

├── requirements.txt       # Python dependencies

# OpenWeatherMap API├── .env                   # Environment variables (create this)

OPENWEATHERMAP_API_KEY=your-api-key├── .gitignore            # Git ignore rules

└── README.md             # This file

# Google Gemini AI```

GEMINI_API_KEY=your-gemini-api-key

```## 🔌 API Endpoints



### 5. Run the Application### Authentication

- `POST /login` - User login

**Development:**- `POST /register` - User registration

```bash- `GET /logout` - User logout

python planner.py

```### Tasks

- `GET /api/tasks` - Get user tasks

**Production (with Gunicorn):**- `POST /api/tasks` - Create new task

```bash- `PUT /api/tasks/<id>` - Update task

gunicorn --bind 0.0.0.0:5000 planner:app- `DELETE /api/tasks/<id>` - Delete task

```

### AI Assistant

Visit `http://localhost:5000` in your browser.- `POST /api/assistant` - Chat with AI assistant



## 🌐 Deployment to Vercel### Weather

- `POST /api/weather` - Get weather by coordinates

### 1. Install Vercel CLI- `GET /api/weather/city/<city>` - Get weather by city

```bash- `GET /api/cities/search` - Search cities

npm i -g vercel

```### Settings

- `GET /api/user-settings` - Get user preferences

### 2. Configure Environment Variables- `POST /api/user-settings` - Update user preferences

Add all environment variables from your `.env` file to Vercel:

- Go to your project settings on Vercel## 🚀 Production Deployment

- Navigate to Environment Variables

- Add each variable### Environment Variables

Set these in your production environment:

### 3. Deploy```env

```bashFLASK_ENV=production

vercel --prodSECRET_KEY=your-production-secret-key

```HOST=0.0.0.0

PORT=5000

### 4. Configure FirebaseFIREBASE_CREDENTIALS_BASE64=base64-encoded-credentials

Add your Vercel domain to Firebase authorized domains:```

1. Go to Firebase Console → Authentication → Settings

2. Add your Vercel domain (e.g., `your-app.vercel.app`)### Using Gunicorn (Recommended)

```bash

## 📱 Mobile App (PWA)pip install gunicorn

gunicorn --bind 0.0.0.0:5000 --workers 4 planner:app

Planno is a Progressive Web App and can be installed on mobile devices:```



### iOS (Safari)### Docker Deployment

1. Visit the app in Safari```dockerfile

2. Tap the Share buttonFROM python:3.9-slim

3. Select "Add to Home Screen"WORKDIR /app

COPY requirements.txt .

### Android (Chrome)RUN pip install -r requirements.txt

1. Visit the app in ChromeCOPY . .

2. Tap the menu (⋮)EXPOSE 5000

3. Select "Add to Home screen"CMD ["gunicorn", "--bind", "0.0.0.0:5000", "planner:app"]

```

## 🎯 Usage

### Platform Deployment

- **Railway** ⭐ RECOMMENDED: Full-featured deployment with persistent processes
  - See [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for detailed guide
  - Supports background scheduler for notifications
  - Built-in metrics and monitoring
  - Auto-deploy from GitHub
  
- **Vercel**: Serverless deployment (notifications via cron jobs)
  - Fast global edge network
  - Automatic HTTPS
  - Limited to serverless functions

- **Heroku**: Ready for deployment with Procfile
- **Google Cloud Platform**: Compatible with App Engine
- **AWS**: Deploy with Elastic Beanstalk or EC2
- **Digital Ocean**: App Platform ready

### Quick Deploy to Railway

1. Fork this repository
2. Sign up at [Railway.app](https://railway.app)
3. Click "New Project" → "Deploy from GitHub"
4. Select your forked repository
5. Add environment variables (see RAILWAY_DEPLOYMENT.md)
6. Deploy! 🚀

Railway is recommended for production use as it supports:
- ✅ Persistent background processes (scheduler)
- ✅ Real-time notifications without external cron
- ✅ Better resource management
- ✅ Built-in monitoring and logging

5. Choose priority and color## 🛠️ Development

6. Click **"Create Task"**

### Local Development

### Managing Schedule```bash

- Click on a **day** in the sidebar to view tasks# Set development environment

- Use **calendar view** for week overviewexport FLASK_ENV=development

- **Edit** tasks by clicking the edit button

- **Delete** tasks individually or all at once# Run with auto-reload

- **Complete** tasks by checking them offpython planner.py

```

### Setting Up Notifications

1. Click the **settings icon**### Testing

2. Enable notifications```bash

3. Choose notification methods (Email/SMS)# Run tests (when available)

4. Set reminder timespython -m pytest tests/

5. Configure daily summary time

# Check code style

### Using AI Assistantflake8 planner.py

1. Click the **assistant button** (💬)```

2. Ask for task suggestions or schedule help

3. AI will analyze your schedule and provide recommendations## 🔒 Security Features



## 🔧 Configuration- **HTTPS Enforcement**: Automatic HTTPS redirects in production

- **Security Headers**: XSS protection, content type validation

### Notification Settings- **Session Security**: Secure cookie configuration

- **Email**: Configure SMTP settings in `.env`- **Input Validation**: Comprehensive data sanitization

- **SMS**: Set up Twilio credentials in `.env`- **Rate Limiting**: API endpoint protection

- **Reminders**: Customize in the settings modal- **CSRF Protection**: Cross-site request forgery prevention



### Weather Location## 📊 Performance

- Default: Auto-detected from IP

- Manual: Search for any city in weather modal- **Firebase Firestore**: Scalable NoSQL database

- **Efficient Caching**: Local storage backup for offline use

### Theme- **Lazy Loading**: Optimized resource loading

- Toggle between light and dark mode- **Minified Assets**: Compressed CSS/JS in production

- Preference saved in browser- **CDN Ready**: Static asset optimization



## 📊 Database Structure## 🤝 Contributing



### Firestore Collections1. Fork the repository

```2. Create a feature branch (`git checkout -b feature/amazing-feature`)

users/3. Commit your changes (`git commit -m 'Add amazing feature'`)

  {userId}/4. Push to the branch (`git push origin feature/amazing-feature`)

    settings/5. Open a Pull Request

      notifications: boolean

      email_notifications: boolean## 📝 License

      sms_notifications: boolean

      theme: stringThis project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

      location: object

    ## 🆘 Support

    tasks/

      {taskId}/### Common Issues

        title: string

        description: string**Firebase Connection Issues**

        day: string- Verify credentials file exists and is valid

        startTime: string- Check Firestore rules allow read/write

        endTime: string- Ensure billing is enabled for Firebase project

        priority: string

        color: string**Email Notifications Not Working**

        completed: boolean- Use App Password for Gmail (not regular password)

        createdAt: timestamp- Check SMTP settings are correct

        updatedAt: timestamp- Verify firewall allows SMTP connections

```

**PWA Not Installing**

## 🤝 Contributing- Ensure HTTPS is enabled

- Check manifest.json is accessible

Contributions are welcome! Please feel free to submit a Pull Request.- Verify service worker registration



1. Fork the repository### Getting Help

2. Create your feature branch (`git checkout -b feature/AmazingFeature`)- 📧 Email: support@dailyplanner.app

3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)- 💬 Discord: [Join our community](https://discord.gg/dailyplanner)

4. Push to the branch (`git push origin feature/AmazingFeature`)- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/issues)

5. Open a Pull Request

## 🔄 Changelog

## 📝 License

### v2.0.0 (Current)

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.- ✅ Production-ready security configuration

- ✅ Environment-based configuration

## 👨‍💻 Author- ✅ Comprehensive documentation

- ✅ PWA optimization

**Chris Buzz**- ✅ Advanced notification system

- GitHub: [@Chris-Buzz](https://github.com/Chris-Buzz)

- Repository: [Daily-Planner](https://github.com/Chris-Buzz/Daily-Planner)### v1.0.0

- ✅ Core task management

## 🙏 Acknowledgments- ✅ Firebase integration

- ✅ Basic AI assistant

- **Firebase** - Authentication and database- ✅ Weather integration

- **Google Gemini AI** - AI assistant capabilities

- **OpenWeatherMap** - Weather data---

- **Twilio** - SMS notifications

- **Vercel** - Hosting and deployment## 💻 Built With

- **Weather Icons** - Weather icon font

- **Backend**: Flask, Python 3.9+

## 📧 Support- **Database**: Firebase Firestore

- **Authentication**: Firebase Auth

If you have any questions or need help, please open an issue on GitHub.- **AI**: Google Gemini 2.5 Flash

- **Notifications**: SMTP, Twilio SMS

## 🔒 Privacy- **Weather**: OpenWeatherMap API

- **Frontend**: Vanilla JavaScript, CSS3

Your data is stored securely in Firebase Firestore with user-level isolation. We never share your personal information. See our [Privacy Policy](https://planno-eta.vercel.app/privacy) for details.- **PWA**: Service Worker, Web Manifest



------



**Made with ❤️ by Chris Buzz****Made with ❤️ for productivity enthusiasts**


*Happy planning! 📅✨*