# CrediSense AI 2.0

### AI-Powered Multi-Credit Card Management & Financial Intelligence Platform

CrediSense AI 2.0 is a full-stack FinTech project designed to help users manage multiple credit cards, track spending, monitor credit utilization, and make better financial decisions.

The project is under active development, with Machine Learning and Deep Learning features planned for future releases.

## Features Implemented

- Add, view, update, and delete credit cards
- Credit utilization calculation
- Total credit limit and outstanding balance tracking
- Interactive financial dashboard
- Add, view, update, and delete transactions
- Transaction history with merchant, category, amount, and date
- SQLite database integration
- REST APIs using FastAPI

## Technology Stack

**Frontend:** HTML5, CSS3, JavaScript

**Backend:** Python, FastAPI, Pydantic, Uvicorn

**Database:** SQLite

**Development Tools:** VS Code, Git, GitHub

## Project Structure

```text
credisenseAI/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── dashboard.html
│   └── requirements.txt
├── .gitignore
└── README.md
```

## How to Run Locally

Clone the repository and enter the backend directory.

```bash
cd credisenseAI/backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Initialize the database:

```bash
python database.py
```

Start the FastAPI server:

```bash
python -m uvicorn main:app --reload
```

Open the dashboard:

`http://127.0.0.1:8000/dashboard`

API documentation:

`http://127.0.0.1:8000/docs`

## Planned Features

- Spending analytics and visualization
- AI-powered credit card recommendations
- Rewards and cashback optimization
- Machine Learning expense prediction
- Deep Learning anomaly detection
- Payment risk analysis
- Secure user authentication
- Cloud deployment

## Current Status

**Work in Progress — Basic Credit Card and Transaction Management Implemented**

This project currently uses a local SQLite database and demo data. It is not yet intended for storing real financial credentials or production financial data.
