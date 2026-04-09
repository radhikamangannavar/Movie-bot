import os, re, requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    raise RuntimeError("Create a .env file with TMDB_API_KEY")

TMDB_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Utility to call TMDB ---
def tmdb_get(path, params=None):
    if params is None: params = {}
    params["api_key"] = TMDB_API_KEY
    r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# Cache genre mapping on first use
GENRE_MAP = None
def load_genres():
    global GENRE_MAP
    if GENRE_MAP is not None:
        return GENRE_MAP
    data = tmdb_get("/genre/movie/list", {"language": "en-US"})
    GENRE_MAP = {g["name"].lower(): g["id"] for g in data.get("genres", [])}
    return GENRE_MAP

def detect_intent(text):
    t = text.lower()
    if re.search(r"\b(more like|similar to)\b", t): return "more_like"
    if re.search(r"\b(detail|details|about|who|what is)\b", t): return "details"
    if re.search(r"\b(popular|popular movies|trending)\b", t): return "popular"
    if re.search(r"\b(top rated|top-rated|toprated)\b", t): return "top_rated"
    if re.search(r"\b(now playing|now_playing|nowplaying|in theatres|in theaters)\b", t): return "now_playing"
    if re.search(r"\b(upcoming)\b", t): return "upcoming"
    if re.search(r"\b(hi|hello|hey|good)\b", t): return "greeting"
    # default to recommend
    if re.search(r"\b(recommend|suggest|watch)\b", t): return "recommend"
    return "recommend"

def extract_genres_and_year(text):
    text_l = text.lower()
    genres = []
    year = None
    genmap = load_genres()
    # simple alias handling
    aliases = {
        "sci-fi": "science fiction", "scifi":"science fiction", "romcom":"romance",
        "romantic": "romance"
    }
    for a,k in aliases.items():
        if a in text_l:
            text_l = text_l.replace(a, k)
    for gname in genmap.keys():
        if gname in text_l:
            genres.append(genmap[gname])
    # find 4-digit year
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        year = int(m.group(0))
    return genres, year

def format_movie(tmdb_item):
    return {
        "id": tmdb_item.get("id"),
        "title": tmdb_item.get("title") or tmdb_item.get("name"),
        "overview": tmdb_item.get("overview"),
        "release_date": tmdb_item.get("release_date"),
        "rating": tmdb_item.get("vote_average"),
        "poster": IMAGE_BASE + tmdb_item["poster_path"] if tmdb_item.get("poster_path") else None,
        "popularity": tmdb_item.get("popularity")
    }

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/message", methods=["POST"])
def api_message():
    data = request.json or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"type":"text","message":"Send me a message like 'Recommend sci-fi movies'."})

    intent = detect_intent(text)
    genres, year = extract_genres_and_year(text)

    try:
        if intent == "greeting":
            return jsonify({"type":"text","message":"Hi! Ask me to recommend movies: e.g., 'Recommend sci-fi movies' or 'Show popular movies'."})

        if intent == "details":
            # try search by title
            q = re.sub(r"\b(details?|about)\b", "", text, flags=re.I).strip()
            if not q:
                return jsonify({"type":"text","message":"Which movie? e.g., 'Details of Inception'."})
            res = tmdb_get("/search/movie", {"query": q, "language": "en-US", "page":1})
            if res["results"]:
                movie = tmdb_get(f"/movie/{res['results'][0]['id']}", {"language":"en-US"})
                return jsonify({"type":"details","movie": format_movie(movie), "raw": movie})
            return jsonify({"type":"text","message":"Couldn't find that movie. Try different title."})

        if intent == "more_like":
            # check if message contains a title; if so, search; else, allow client to pass movie_id
            # try find a quoted title or the text after 'more like'
            m = re.search(r"more like (.+)", text, flags=re.I)
            if m:
                q = m.group(1).strip()
                res = tmdb_get("/search/movie", {"query": q, "language":"en-US", "page":1})
                if res["results"]:
                    movie_id = res["results"][0]["id"]
                else:
                    return jsonify({"type":"text","message":"Couldn't find that base movie to find similar ones."})
            else:
                movie_id = data.get("movie_id")
                if not movie_id:
                    return jsonify({"type":"text","message":"Tell me which movie or click 'More like this' on a result."})
            sim = tmdb_get(f"/movie/{movie_id}/similar", {"language":"en-US", "page":1})
            items = [format_movie(x) for x in sim.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"similar","results": items})

        # Popular / top rated / now playing / upcoming
        if intent == "popular":
            res = tmdb_get("/movie/popular", {"language":"en-US", "page":1})
            items = [format_movie(x) for x in res.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"popular","results": items})
        if intent == "top_rated":
            res = tmdb_get("/movie/top_rated", {"language":"en-US", "page":1})
            items = [format_movie(x) for x in res.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"top_rated","results": items})
        if intent == "now_playing":
            res = tmdb_get("/movie/now_playing", {"language":"en-US", "page":1})
            items = [format_movie(x) for x in res.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"now_playing","results": items})
        if intent == "upcoming":
            res = tmdb_get("/movie/upcoming", {"language":"en-US", "page":1})
            items = [format_movie(x) for x in res.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"upcoming","results": items})

        # Default: recommend (possibly by genre or year)
        if genres:
            with_genres = ",".join(map(str, genres))
            params = {"with_genres": with_genres, "sort_by": "popularity.desc", "language":"en-US", "page":1}
            if year:
                params["primary_release_year"] = year
            res = tmdb_get("/discover/movie", params)
            items = [format_movie(x) for x in res.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"discover","results": items})
        else:
            # fallback: search by keywords if there are nouns in text
            q = re.sub(r"(recommend|suggest|movies|movie|please|for|me|some|popular|top|show)", "", text, flags=re.I).strip()
            if q:
                res = tmdb_get("/search/movie", {"query": q, "language":"en-US", "page":1})
                if res["results"]:
                    items = [format_movie(x) for x in res["results"][:6]]
                    return jsonify({"type":"recommend","source":"search","results": items})
            # final fallback: popular
            res = tmdb_get("/movie/popular", {"language":"en-US", "page":1})
            items = [format_movie(x) for x in res.get("results", [])[:6]]
            return jsonify({"type":"recommend","source":"popular_fallback","results": items})
    except requests.HTTPError as e:
        return jsonify({"type":"error","message":"TMDB API error: " + str(e)}), 500
    except Exception as e:
        return jsonify({"type":"error","message":"Server error: " + str(e)}), 500

@app.route("/api/movie/<int:movie_id>", methods=["GET"])
def api_movie_details(movie_id):
    try:
        movie = tmdb_get(f"/movie/{movie_id}", {"language":"en-US"})
        return jsonify({"movie": format_movie(movie), "raw": movie})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/movie/<int:movie_id>/similar", methods=["GET"])
def api_movie_similar(movie_id):
    try:
        sim = tmdb_get(f"/movie/{movie_id}/similar", {"language":"en-US", "page":1})
        items = [format_movie(x) for x in sim.get("results", [])[:6]]
        return jsonify({"results": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
