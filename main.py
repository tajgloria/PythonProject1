import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import abort

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "development-key-change-this")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "nonprofithub.db")

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()

    try:

        db.executescript("""
                         
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         
            );
            
            CREATE TABLE IF NOT EXISTS opportunities (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              description TEXT NOT NULL,
              location TEXT NOT NULL,
              date TEXT NOT NULL,
              organization TEXT NOT NULL
            
            );
            
            CREATE TABLE IF NOT EXISTS signups (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              opportunity_id INTEGER NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, opportunity_id),
              FOREIGN KEY (user_id) 
                REFERENCES users (id)
              FOREIGN KEY (opportunity_id)
                REFERENCES opportunities (id) 
                
            );
            
            CREATE TABLE IF NOT EXISTS hours (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              activity TEXT NOT NULL,
              volunteer_date TEXT NOT NULL,
              duration REAL NOT NULL,
              notes TEXT,
              approved INTEGER DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(user_id) 
                  REFERENCES users (id)
                  
            );
            
        """)

        db.commit()

    finally:
        db.close()
