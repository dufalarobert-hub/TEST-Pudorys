"""
Vercel Python entry-point. Vystaví Flask `app` ako WSGI funkciu.
Všetky routy sú presmerované sem cez vercel.json rewrites.
"""
import os
import sys

# pridaj koreň repa do path, nech vieme importovať app.py a moduly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (Flask WSGI aplikácia)
