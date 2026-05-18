from flask import Flask, request, session, redirect, url_for, render_template
import mysql.connector
from mysql.connector import pooling
import os
from werkzeug.utils import secure_filename
from flask import jsonify

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db_pool = pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=10,  # increased from 5 to 10
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    port=int(os.getenv("MYSQLPORT", 3306))
)

def get_db():
    return db_pool.get_connection()


@app.route("/", methods=["GET", "POST"])
def login():
    msg = ""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username and password:
            conn = get_db()
            cursor = conn.cursor(dictionary=True, buffered=True)
            try:
                sql = "SELECT * FROM users WHERE username=%s AND password=%s"
                cursor.execute(sql, (username, password,))
                account = cursor.fetchone()
            finally:
                cursor.close()
                conn.close()

            if account:
                session["logginid"] = account["id"]
                session["username"] = account["username"]
                session["password"] = account["password"]
                return redirect(url_for("dashboard"))
            else:
                msg = "Incorrect username or password"
        else:
            msg = "Fill both username and password"

    return render_template("login.html", msg=msg)


@app.route("/registration", methods=["GET", "POST"])
def registration():
    msg = ""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username and password:
            conn = get_db()
            cursor = conn.cursor(dictionary=True, buffered=True)
            try:
                sql = "SELECT * FROM users WHERE username=%s"
                cursor.execute(sql, (username,))
                account = cursor.fetchone()

                if account:
                    msg = "You already have an account"
                else:
                    sql = "INSERT INTO users (username, password) VALUES(%s, %s)"
                    cursor.execute(sql, (username, password,))
                    conn.commit()
                    msg = "You have registered successfully"
            finally:
                cursor.close()
                conn.close()
        else:
            msg = "Type both username and password"

    return render_template("registration.html", msg=msg)


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = """
        SELECT
        posts.id, 
        posts.photo, 
        users.profile_photo, 
        users.username, 
        users.name,
        count(likes.id) as like_count,
        sum(
             case
                 when likes.username = %s then 1
                 else 0
              end
        ) as liked_by_user
        FROM posts
        JOIN users ON posts.username = users.username
        left join likes on posts.id = likes.post_id
        WHERE posts.photo IS NOT NULL
        AND (
            posts.username = %s
            OR posts.username IN (
                SELECT 
                CASE 
                    WHEN from_user = %s THEN to_user
                    ELSE from_user
                END
                FROM friends
                WHERE from_user = %s OR to_user = %s
            )
        )
        group by posts.id, posts.photo, users.profile_photo, users.username, users.name
        ORDER BY posts.id DESC
        """
        cursor.execute(sql, (session["username"], session["username"], session["username"], session["username"], session["username"],))
        posts = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("dashboard.html", posts=posts)


@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "SELECT IFNULL(profile_photo, 'default.png') AS profile_photo FROM users WHERE username=%s"
        cursor.execute(sql, (username,))
        user = cursor.fetchone()

        sql = "SELECT name, about FROM users WHERE username=%s"
        cursor.execute(sql, (username,))
        user1 = cursor.fetchone()

        sql = """
        SELECT 
        users.*,
        CASE
             WHEN friend_request.from_user IS NOT NULL THEN 1
             ELSE 0
        END AS friend_request_by_user,
        CASE 
           WHEN friends.from_user IS NOT NULL THEN 1
           ELSE 0
        END AS already_friends
        FROM users
        LEFT JOIN friend_request
        ON users.username = friend_request.to_user
        AND friend_request.from_user = %s  
        LEFT JOIN friends
        ON (
            (friends.from_user = %s AND friends.to_user = users.username)
            OR
            (friends.to_user = %s AND friends.from_user = users.username)
        )
        WHERE users.username = %s
        """
        cursor.execute(sql, (session["username"], session["username"], session["username"], username,))
        req = cursor.fetchone()

        sql = """
        SELECT 
        users.username,
        users.profile_photo,
        users.name,
        friend_request.*
        FROM users
        JOIN friend_request ON users.username = friend_request.from_user
        WHERE friend_request.to_user=%s
        """
        cursor.execute(sql, (session["username"],))
        datas = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("profile.html", user=user, user1=user1, username=username, logged_user=session["username"], request=req, datas=datas)


@app.route("/profile_edit", methods=["GET", "POST"])
def profile_edit():
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        if request.method == "POST":
            file = request.files.get("photo")

            if file and file.filename != "":
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                sql = "UPDATE users SET profile_photo=%s WHERE username=%s AND password=%s"
                cursor.execute(sql, (filename, session["username"], session["password"],))
                conn.commit()

            name = request.form.get("name")
            about = request.form.get("about")

            if name and about:
                sql = "UPDATE users SET name=%s, about=%s WHERE username=%s AND password=%s"
                cursor.execute(sql, (name, about, session["username"], session["password"],))
                conn.commit()

        sql = "SELECT profile_photo FROM users WHERE username=%s AND password=%s"
        cursor.execute(sql, (session["username"], session["password"],))
        user = cursor.fetchone()

        sql = "SELECT name, about FROM users WHERE username=%s AND password=%s"
        cursor.execute(sql, (session["username"], session["password"]))
        user1 = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    return render_template("profile_edit.html", user=user, user1=user1)


@app.route("/home", methods=["GET", "POST"])
def home():
    return redirect(url_for("dashboard"))


@app.route("/add_a_post", methods=["GET", "POST"])
def add_a_post():
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        if request.method == "POST":
            file = request.files.get("photo")

            if file and file.filename != "":
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                sql = "INSERT INTO posts (username, photo) VALUES(%s, %s)"
                cursor.execute(sql, (session["username"], filename))
                conn.commit()

        sql = "SELECT photo FROM posts WHERE username=%s ORDER BY id DESC LIMIT 1"
        cursor.execute(sql, (session["username"],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    return render_template("add_a_post.html", user=user)


@app.route("/profile_photos/<username>", methods=["GET", "POST"])
def profile_photos(username):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "SELECT id, photo FROM posts WHERE username=%s AND photo IS NOT NULL AND photo != ''"
        cursor.execute(sql, (username,))
        users = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("profile_photos.html", users=users, profile_owner=username, logged_user=session["username"])


@app.route("/delete_photo", methods=["POST"])
def delete_photo():
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        photo_id = request.form["photo_id"]
        sql = "DELETE FROM posts WHERE id=%s"
        cursor.execute(sql, (photo_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect("/profile_photos/" + session["username"])


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        name = request.form.get("name")

        if name:
            conn = get_db()
            cursor = conn.cursor(dictionary=True, buffered=True)
            try:
                sql = "SELECT name, username FROM users WHERE name=%s"
                cursor.execute(sql, (name,))
                user = cursor.fetchone()
            finally:
                cursor.close()
                conn.close()

            if user:
                return redirect(url_for("profile", username=user["username"]))

    return redirect("/dashboard")


@app.route("/like/<int:post_id>", methods=["POST"])
def like(post_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        username = session["username"]

        sql = "SELECT * FROM likes WHERE post_id=%s AND username=%s"
        cursor.execute(sql, (post_id, username,))
        existing_like = cursor.fetchone()

        if existing_like:
            sql = "DELETE FROM likes WHERE post_id=%s AND username=%s"
            cursor.execute(sql, (post_id, username,))
            liked = False
        else:
            sql = "INSERT INTO likes(post_id, username) VALUES(%s, %s)"
            cursor.execute(sql, (post_id, username,))
            liked = True

        conn.commit()

        sql = "SELECT COUNT(*) AS total FROM likes WHERE post_id=%s"
        cursor.execute(sql, (post_id,))
        total_likes = cursor.fetchone()["total"]
    finally:
        cursor.close()
        conn.close()

    return jsonify({"liked": liked, "total_likes": total_likes})


@app.route("/comment_save/<int:comment_id>", methods=["GET", "POST"])
def comment_save(comment_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        if request.method == "POST":
            comment = request.form.get("comment")

            if comment:
                sql = "INSERT INTO comments(comment_id, comment, username) VALUES(%s, %s, %s)"
                cursor.execute(sql, (comment_id, comment, session["username"],))
                conn.commit()

                cursor.close()
                conn.close()

                return redirect(url_for("comment_save", comment_id=comment_id))

        sql = """
        SELECT comments.comment,
        comments.username,
        users.profile_photo,
        users.name
        FROM comments
        JOIN users ON comments.username = users.username
        WHERE comments.comment_id=%s
        ORDER BY comments.id ASC
        """
        cursor.execute(sql, (comment_id,))
        comments = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("comment.html", comments=comments)


@app.route("/friends/<user>", methods=["GET", "POST"])
def friends(user):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "INSERT INTO friends(from_user, to_user) VALUES(%s, %s)"
        cursor.execute(sql, (user, session["username"],))

        sql = "DELETE FROM friend_request WHERE from_user=%s AND to_user=%s"
        cursor.execute(sql, (user, session["username"],))

        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return jsonify({"success": True})


@app.route("/friend_request/<to_user>", methods=["GET", "POST"])
def friend_request(to_user):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "SELECT * FROM friend_request WHERE to_user=%s AND from_user=%s"
        cursor.execute(sql, (to_user, session["username"],))
        requests = cursor.fetchone()

        if requests:
            sql = "DELETE FROM friend_request WHERE to_user=%s AND from_user=%s"
            cursor.execute(sql, (to_user, session["username"],))
        else:
            sql = "INSERT INTO friend_request(to_user, from_user) VALUES(%s, %s)"
            cursor.execute(sql, (to_user, session["username"],))

        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("profile", username=to_user))


@app.route("/my_friends/<username>", methods=["GET", "POST"])
def my_friends(username):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = """
        SELECT 
        users.username, users.profile_photo, users.name, friends.*
        FROM users
        JOIN friends ON users.username = friends.from_user
        AND friends.to_user = %s
        """
        cursor.execute(sql, (username,))
        datas2 = cursor.fetchall()

        sql = """
        SELECT 
        users.username, users.profile_photo, users.name, friends.*
        FROM users
        JOIN friends ON users.username = friends.to_user
        AND friends.from_user = %s
        """
        cursor.execute(sql, (username,))
        datas3 = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("my_friends.html", datas2=datas2, logged_in_user=session["username"], username=username, datas3=datas3)


@app.route("/notifications", methods=["GET", "POST"])
def notifications():
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = """
        SELECT 
        users.username, users.profile_photo, users.name, friends.*
        FROM users
        JOIN friends ON users.username = friends.to_user
        AND friends.from_user = %s
        """
        cursor.execute(sql, (session["username"],))
        datas = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("notifications.html", datas=datas)


@app.route("/delete_request/<from_user>", methods=["GET", "POST"])
def delete_request(from_user):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "DELETE FROM friend_request WHERE from_user=%s AND to_user=%s"
        cursor.execute(sql, (from_user, session["username"]))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("profile", username=session["username"]))


@app.route("/make_unfriend1/<from_user>", methods=["GET", "POST"])
def make_unfriend1(from_user):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "DELETE FROM friends WHERE from_user=%s AND to_user=%s"
        cursor.execute(sql, (from_user, session["username"]))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("my_friends", username=session["username"]))


@app.route("/make_unfriend2/<to_user>", methods=["GET", "POST"])
def make_unfriend2(to_user):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "DELETE FROM friends WHERE from_user=%s AND to_user=%s"
        cursor.execute(sql, (session["username"], to_user))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("my_friends", username=session["username"]))


@app.route("/deletePost/<int:postid>", methods=["GET", "POST"])
def deletePost(postid):
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        sql = "DELETE FROM posts WHERE posts.id=%s AND username=%s"
        cursor.execute(sql, (postid, session["username"],))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return jsonify({"delete": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


# from flask import Flask, request, session, redirect, url_for, render_template
# import mysql.connector
# from mysql.connector import pooling
# import os
# from werkzeug.utils import secure_filename
# from flask import jsonify

# app = Flask(__name__)

# app.secret_key = os.getenv("SECRET_KEY")

# UPLOAD_FOLDER = "static/uploads"
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# db_pool = pooling.MySQLConnectionPool(
#     pool_name="mypool",
#     pool_size=5,
#     host=os.getenv("DB_HOST"),
#     user=os.getenv("DB_USER"),
#     password=os.getenv("DB_PASSWORD"),
#     database=os.getenv("DB_NAME"),
#     port=int(os.getenv("MYSQLPORT", 3306))
# )

# def get_db():
#     return db_pool.get_connection()


# @app.route("/", methods=["GET", "POST"])
# def login():
#     msg = ""

#     if request.method == "POST":
#         username = request.form.get("username")
#         password = request.form.get("password")

#         if username and password:
#             conn = get_db()
#             cursor = conn.cursor(dictionary=True, buffered=True)

#             sql = "SELECT * FROM users WHERE username=%s AND password=%s"
#             cursor.execute(sql, (username, password,))
#             account = cursor.fetchone()

#             cursor.close()
#             conn.close()

#             if account:
#                 session["logginid"] = account["id"]
#                 session["username"] = account["username"]
#                 session["password"] = account["password"]
#                 return redirect(url_for("dashboard"))
#             else:
#                 msg = "Incorrect username or password"
#         else:
#             msg = "Fill both username and password"

#     return render_template("login.html", msg=msg)


# @app.route("/registration", methods=["GET", "POST"])
# def registration():
#     msg = ""

#     if request.method == "POST":
#         username = request.form.get("username")
#         password = request.form.get("password")

#         if username and password:
#             conn = get_db()
#             cursor = conn.cursor(dictionary=True, buffered=True)

#             sql = "SELECT * FROM users WHERE username=%s"
#             cursor.execute(sql, (username,))
#             account = cursor.fetchone()

#             if account:
#                 msg = "You already have an account"
#             else:
#                 sql = "INSERT INTO users (username, password) VALUES(%s, %s)"
#                 cursor.execute(sql, (username, password,))
#                 conn.commit()
#                 msg = "You have registered successfully"

#             cursor.close()
#             conn.close()
#         else:
#             msg = "Type both username and password"

#     return render_template("registration.html", msg=msg)


# @app.route("/dashboard", methods=["GET", "POST"])
# def dashboard():
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     sql = """
#     SELECT
#     posts.id, 
#     posts.photo, 
#     users.profile_photo, 
#     users.username, 
#     users.name,

#     count(likes.id) as like_count,

#     sum(
#          case
#              when likes.username = %s then 1
#              else 0
#           end
#     ) as liked_by_user

#     FROM posts

#     JOIN users
#     ON posts.username = users.username

#     left join likes
#     on posts.id = likes.post_id
  
#     WHERE posts.photo IS NOT NULL
#     AND (
#         posts.username = %s
#         OR posts.username IN (
#             SELECT 
#             CASE 
#                 WHEN from_user = %s THEN to_user
#                 ELSE from_user
#             END
#             FROM friends
#             WHERE from_user = %s OR to_user = %s
#         )
#     )

#     group by 
#     posts.id,
#     posts.photo,
#     users.profile_photo,
#     users.username,
#     users.name

#     ORDER BY posts.id DESC
#     """
#     cursor.execute(sql, (session["username"], session["username"], session["username"], session["username"], session["username"],))
#     posts = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return render_template("dashboard.html", posts=posts)


# @app.route("/profile/<username>", methods=["GET", "POST"])
# def profile(username):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     sql = "SELECT IFNULL(profile_photo, 'default.png') AS profile_photo FROM users WHERE username=%s"
#     cursor.execute(sql, (username,))
#     user = cursor.fetchone()

#     sql = "SELECT name, about FROM users WHERE username=%s"
#     cursor.execute(sql, (username,))
#     user1 = cursor.fetchone()

#     sql = """
#     SELECT 
#     users.*,

#     CASE
#          WHEN friend_request.from_user IS NOT NULL THEN 1
#          ELSE 0
#     END AS friend_request_by_user,

#     CASE 
#        WHEN friends.from_user IS NOT NULL THEN 1
#        ELSE 0
#     END AS already_friends

#     FROM users

#     LEFT JOIN friend_request
#     ON users.username = friend_request.to_user
#     AND friend_request.from_user = %s  

#     LEFT JOIN friends
#     ON (
#         (friends.from_user = %s AND friends.to_user = users.username)
#         OR
#         (friends.to_user = %s AND friends.from_user = users.username)
#     )

#     WHERE users.username = %s
#     """
#     cursor.execute(sql, (session["username"], session["username"], session["username"], username,))
#     req = cursor.fetchone()

#     sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friend_request.*

#     FROM users
#     JOIN friend_request
#     ON users.username = friend_request.from_user

#     WHERE friend_request.to_user=%s
#     """
#     cursor.execute(sql, (session["username"],))
#     datas = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return render_template("profile.html", user=user, user1=user1, username=username, logged_user=session["username"], request=req, datas=datas)


# @app.route("/profile_edit", methods=["GET", "POST"])
# def profile_edit():
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     if request.method == "POST":
#         file = request.files.get("photo")

#         if file and file.filename != "":
#             filename = secure_filename(file.filename)
#             filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#             file.save(filepath)

#             sql = "UPDATE users SET profile_photo=%s WHERE username=%s AND password=%s"
#             cursor.execute(sql, (filename, session["username"], session["password"],))
#             conn.commit()

#         name = request.form.get("name")
#         about = request.form.get("about")

#         if name and about:
#             sql = "UPDATE users SET name=%s, about=%s WHERE username=%s AND password=%s"
#             cursor.execute(sql, (name, about, session["username"], session["password"],))
#             conn.commit()

#     sql = "SELECT profile_photo FROM users WHERE username=%s AND password=%s"
#     cursor.execute(sql, (session["username"], session["password"],))
#     user = cursor.fetchone()

#     sql = "SELECT name, about FROM users WHERE username=%s AND password=%s"
#     cursor.execute(sql, (session["username"], session["password"]))
#     user1 = cursor.fetchone()

#     cursor.close()
#     conn.close()

#     return render_template("profile_edit.html", user=user, user1=user1)


# @app.route("/home", methods=["GET", "POST"])
# def home():
#     return redirect(url_for("dashboard"))


# @app.route("/add_a_post", methods=["GET", "POST"])
# def add_a_post():
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     if request.method == "POST":
#         file = request.files.get("photo")

#         if file and file.filename != "":
#             filename = secure_filename(file.filename)
#             filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#             file.save(filepath)

#             sql = "INSERT INTO posts (username, photo) VALUES(%s, %s)"
#             cursor.execute(sql, (session["username"], filename))
#             conn.commit()

#     sql = "SELECT photo FROM posts WHERE username=%s ORDER BY id DESC LIMIT 1"
#     cursor.execute(sql, (session["username"],))
#     user = cursor.fetchone()

#     cursor.close()
#     conn.close()

#     return render_template("add_a_post.html", user=user)


# @app.route("/profile_photos/<username>", methods=["GET", "POST"])
# def profile_photos(username):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     sql = "SELECT id, photo FROM posts WHERE username=%s AND photo IS NOT NULL AND photo != ''"
#     cursor.execute(sql, (username,))
#     users = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return render_template("profile_photos.html", users=users, profile_owner=username, logged_user=session["username"])


# @app.route("/delete_photo", methods=["POST"])
# def delete_photo():
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     photo_id = request.form["photo_id"]

#     sql = "DELETE FROM posts WHERE id=%s"
#     cursor.execute(sql, (photo_id,))
#     conn.commit()

#     cursor.close()
#     conn.close()

#     return redirect("/profile_photos/" + session["username"])


# @app.route("/search", methods=["GET", "POST"])
# def search():
#     if request.method == "POST":
#         name = request.form.get("name")

#         if name:
#             conn = get_db()
#             cursor = conn.cursor(dictionary=True, buffered=True)

#             sql = "SELECT name, username FROM users WHERE name=%s"
#             cursor.execute(sql, (name,))
#             user = cursor.fetchone()

#             cursor.close()
#             conn.close()

#             if user:
#                 return redirect(url_for("profile", username=user["username"]))

#     return redirect("/dashboard")


# @app.route("/like/<int:post_id>", methods=["POST"])
# def like(post_id):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     username = session["username"]

#     sql = "SELECT * FROM likes WHERE post_id=%s AND username=%s"
#     cursor.execute(sql, (post_id, username,))
#     existing_like = cursor.fetchone()

#     if existing_like:
#         sql = "DELETE FROM likes WHERE post_id=%s AND username=%s"
#         cursor.execute(sql, (post_id, username,))
#         liked = False
#     else:
#         sql = "INSERT INTO likes(post_id, username) VALUES(%s, %s)"
#         cursor.execute(sql, (post_id, username,))
#         liked = True

#     conn.commit()

#     sql = "SELECT COUNT(*) AS total FROM likes WHERE post_id=%s"
#     cursor.execute(sql, (post_id,))
#     total_likes = cursor.fetchone()["total"]

#     cursor.close()
#     conn.close()

#     return jsonify({"liked": liked, "total_likes": total_likes})


# @app.route("/comment_save/<int:comment_id>", methods=["GET", "POST"])
# def comment_save(comment_id):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     if request.method == "POST":
#         comment = request.form.get("comment")

#         if comment:
#             sql = "INSERT INTO comments(comment_id, comment, username) VALUES(%s, %s, %s)"
#             cursor.execute(sql, (comment_id, comment, session["username"],))
#             conn.commit()

#             cursor.close()
#             conn.close()

#             return redirect(url_for("comment_save", comment_id=comment_id))

#     sql = """
#     SELECT comments.comment,
#     comments.username,
#     users.profile_photo,
#     users.name

#     FROM comments

#     JOIN users
#     ON comments.username = users.username

#     WHERE comments.comment_id=%s

#     ORDER BY comments.id ASC
#     """
#     cursor.execute(sql, (comment_id,))
#     comments = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return render_template("comment.html", comments=comments)


# @app.route("/friends/<user>", methods=["GET", "POST"])
# def friends(user):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = "INSERT INTO friends(from_user, to_user) VALUES(%s, %s)"
#     cursor.execute(sql, (user, session["username"],))

#     sql = "DELETE FROM friend_request WHERE from_user=%s AND to_user=%s"
#     cursor.execute(sql, (user, session["username"],))

#     conn.commit()

#     cursor.close()
#     conn.close()

#     return jsonify({"success": True})


# @app.route("/friend_request/<to_user>", methods=["GET", "POST"])
# def friend_request(to_user):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = "SELECT * FROM friend_request WHERE to_user=%s AND from_user=%s"
#     cursor.execute(sql, (to_user, session["username"],))
#     requests = cursor.fetchone()

#     if requests:
#         sql = "DELETE FROM friend_request WHERE to_user=%s AND from_user=%s"
#         cursor.execute(sql, (to_user, session["username"],))
#     else:
#         sql = "INSERT INTO friend_request(to_user, from_user) VALUES(%s, %s)"
#         cursor.execute(sql, (to_user, session["username"],))

#     conn.commit()

#     cursor.close()
#     conn.close()

#     return redirect(url_for("profile", username=to_user))


# @app.route("/my_friends/<username>", methods=["GET", "POST"])
# def my_friends(username):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friends.*

#     FROM users
    
#     JOIN friends
#     ON users.username = friends.from_user
#     AND friends.to_user = %s
#     """
#     cursor.execute(sql, (username,))
#     datas2 = cursor.fetchall()

#     sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friends.*

#     FROM users
    
#     JOIN friends
#     ON users.username = friends.to_user
#     AND friends.from_user = %s
#     """
#     cursor.execute(sql, (username,))
#     datas3 = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return render_template("my_friends.html", datas2=datas2, logged_in_user=session["username"], username=username, datas3=datas3)


# @app.route("/notifications", methods=["GET", "POST"])
# def notifications():
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True, buffered=True)

#     sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friends.*

#     FROM users
    
#     JOIN friends
#     ON users.username = friends.to_user
#     AND friends.from_user = %s
#     """
#     cursor.execute(sql, (session["username"],))
#     datas = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return render_template("notifications.html", datas=datas)


# @app.route("/delete_request/<from_user>", methods=["GET", "POST"])
# def delete_request(from_user):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = "DELETE FROM friend_request WHERE from_user=%s AND to_user=%s"
#     cursor.execute(sql, (from_user, session["username"]))
#     conn.commit()

#     cursor.close()
#     conn.close()

#     return redirect(url_for("profile", username=session["username"]))


# @app.route("/make_unfriend1/<from_user>", methods=["GET", "POST"])
# def make_unfriend1(from_user):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = "DELETE FROM friends WHERE from_user=%s AND to_user=%s"
#     cursor.execute(sql, (from_user, session["username"]))
#     conn.commit()

#     cursor.close()
#     conn.close()

#     return redirect(url_for("my_friends", username=session["username"]))


# @app.route("/make_unfriend2/<to_user>", methods=["GET", "POST"])
# def make_unfriend2(to_user):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = "DELETE FROM friends WHERE from_user=%s AND to_user=%s"
#     cursor.execute(sql, (session["username"], to_user))
#     conn.commit()

#     cursor.close()
#     conn.close()

#     return redirect(url_for("my_friends", username=session["username"]))


# @app.route("/deletePost/<int:postid>", methods=["GET", "POST"])
# def deletePost(postid):
#     conn = get_db()
#     cursor = conn.cursor(dictionary=True)

#     sql = "DELETE FROM posts WHERE posts.id=%s AND username=%s"
#     cursor.execute(sql, (postid, session["username"],))
#     conn.commit()

#     cursor.close()
#     conn.close()

#     return jsonify({"delete": True})


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


# from flask import Flask, request, session, redirect, url_for, render_template
# import mysql.connector
# import os
# from werkzeug.utils import secure_filename
# from flask import jsonify

# app = Flask(__name__)
# # app.secret_key = "secretkey"

# # db = mysql.connector.connect(
# #    host="localhost",
# #    user ="root",
# #    password = "121997",
# #    database = "facebook_clone",
# #    autocommit=True
# # )

# db = mysql.connector.connect(
#    host=os.getenv("DB_HOST"),
#    user=os.getenv("DB_USER"),
#    password=os.getenv("DB_PASSWORD"),
#    database=os.getenv("DB_NAME"),
#    port=int(os.getenv("MYSQLPORT", 3306))
# )

# # def get_db():
# #     if not hasattr(get_db, 'conn') or not get_db.conn.is_connected():
# #         get_db.conn = mysql.connector.connect(
# #             host=os.getenv("DB_HOST"),
# #             user=os.getenv("DB_USER"),
# #             password=os.getenv("DB_PASSWORD"),
# #             database=os.getenv("DB_NAME"),
# #             port=int(os.getenv("MYSQLPORT", 3306))
# #         )
# #     return get_db.conn

# # db = mysql.connector.connect(
# #     host=os.getenv("MYSQLHOST"),
# #     user=os.getenv("MYSQLUSER"),
# #     password=os.getenv("MYSQLPASSWORD"),
# #     database=os.getenv("MYSQLDATABASE"),
# #     port=int(os.getenv("MYSQLPORT"))
# # )

# app.secret_key = os.getenv("SECRET_KEY")

# UPLOAD_FOLDER = "static/uploads"
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# cursor = db.cursor()

# @app.route("/", methods=["GET", "POST"])
# def login():
#     msg = ""

#     if request.method=="POST":
#        username=request.form.get("username")
#        password=request.form.get("password")

#        if username and password:
#           cursor = db.cursor(dictionary=True, buffered=True)

#           sql= "select * from users where username=%s and password=%s"
#           cursor.execute(sql, (username, password,))
#           account=cursor.fetchone()

#           if account:
#              session["logginid"] = account["id"]
#              session["username"] = account["username"]
#              session["password"] = account['password']
#              cursor.close()
            
#              return redirect(url_for("dashboard",))
#           else:
#              msg = "Incorrect username or password"
#        else:
#           msg = "Fill both username and password"
          
#     return render_template("login.html", msg=msg)

# @app.route("/registration", methods=["GET", "POST"])
# def registration():
#     msg=""

#     if request.method=="POST":
#        username=request.form.get("username")
#        password=request.form.get("password")
#        print(username, password)

#        if username and password:
#           cursor=db.cursor(dictionary=True, buffered=True)

#           sql="select * from users where username=%s"
#           cursor.execute(sql, (username,))
#           account=cursor.fetchone()

#           if account:
#              msg ="You already have an account"
#           else:
#              sql="insert into users (username, password) values(%s, %s)"
#              cursor.execute(sql, (username, password,))
             
#              db.commit()
#              msg= "You have registered successfully"
#        else:
#           msg="Type both username and password"

#     return render_template("registration.html", msg=msg)

# @app.route("/dashboard", methods=["GET", "POST"])
# def dashboard():

#    cursor=db.cursor(dictionary=True, buffered=True)

#    sql = """
#    SELECT
#    posts.id, 
#    posts.photo, 
#    users.profile_photo, 
#    users.username, 
#    users.name,

#    count(likes.id) as like_count,

#    sum(
#         case
#             when likes.username = %s then 1
#             else 0
#          end
#    ) as liked_by_user

#    FROM posts

#    JOIN users
#    ON posts.username = users.username

#    left join likes
#    on posts.id = likes.post_id
  
#    WHERE posts.photo IS NOT NULL
#    AND (
#     posts.username = %s

#     OR posts.username IN (
#         SELECT 
#         CASE 
#             WHEN from_user = %s THEN to_user
#             ELSE from_user
#         END
#         FROM friends
#         WHERE from_user = %s OR to_user = %s
#     )
# )

#    group by 
#    posts.id,
#    posts.photo,
#    users.profile_photo,
#    users.username,
#    users.name

#    ORDER BY posts.id DESC
#    """
#    cursor.execute(sql, (session["username"], session["username"], session["username"], session["username"], session["username"],))
#    posts = cursor.fetchall()
#    print(posts)

#    return render_template("dashboard.html", posts=posts)

# @app.route("/profile/<username>", methods=["GET", "POST"])
# def profile(username):
   
#    cursor=db.cursor(dictionary=True, buffered=True)

#    # sql = "select ifnull(profile_photo, 'default.png') as profile_photo from users where username=%s and password=%s"
#    # cursor.execute(sql, (session["username"], session["password"],))
#    # user=cursor.fetchone()

#    # sql = "select name, about from users where username=%s and password=%s"
#    # cursor.execute(sql, (session["username"], session["password"]))
#    # user1=cursor.fetchone()

#    sql = "select ifnull(profile_photo, 'default.png') as profile_photo from users where username=%s"
#    cursor.execute(sql, (username,))
#    user=cursor.fetchone()

#    sql = "select name, about from users where username=%s"
#    cursor.execute(sql, (username,))
#    user1=cursor.fetchone()

#    sql = """
#     SELECT 
#     users.*,

#     CASE
#          WHEN friend_request.from_user IS NOT NULL THEN 1
#          ELSE 0
#     END AS friend_request_by_user,

#     case 
#        when friends.from_user is not null then 1
#        else 0
#     end as already_friends

#     FROM users

#     LEFT JOIN friend_request
#     ON users.username = friend_request.to_user
#     AND friend_request.from_user = %s  

#    LEFT JOIN friends
#    ON (
#     (friends.from_user = %s AND friends.to_user = users.username)
#     OR
#     (friends.to_user = %s AND friends.from_user = users.username)
#     )

#     WHERE users.username = %s
#     """
#    cursor.execute(sql, (session["username"], session["username"], session["username"], username,))
#    request=cursor.fetchone()
#    print(request)
   
#    sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friend_request.*

#     FROM users
#     JOIN friend_request
#     ON users.username = friend_request.from_user

#     where friend_request.to_user=%s
#     """
#    cursor.execute(sql, (session["username"],))
#    datas=cursor.fetchall()

#    return render_template("profile.html", user=user, user1=user1, username=username, logged_user=session['username'], request=request, datas=datas)

#    # sql = """(
#    #             case 
#    #                 when friend_request.username=%s then 1
#    #                 else 0
#    #               end
#    # ) as friend_request_by_user

#    #  FROM users
#    #  LEFT JOIN friend_request 
#    #  ON users.username = friend_request.to_user
#    #  """

# @app.route("/profile_edit", methods=["GET", "POST"])
# def profile_edit():
#    cursor=db.cursor(dictionary=True, buffered=True)

#    if request.method == "POST":
#     file = request.files.get("photo")

#     if file and file.filename != "":
#        filename = secure_filename(file.filename)
#        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#        file.save(filepath)

#        sql = "update users set profile_photo=%s where username=%s and password=%s"
#        cursor.execute(sql, (filename, session["username"], session["password"],))
#        db.commit()

#    sql = "select profile_photo from users where username=%s and password=%s"
#    cursor.execute(sql, (session["username"], session["password"],))
#    user=cursor.fetchone()

#    if request.method == "POST":
#     name=request.form.get('name')
#     about=request.form.get('about')

#     if name and about:
#        cursor=db.cursor(dictionary=True, buffered=True)
       
#        sql = "update users set name=%s, about=%s where username=%s and password=%s"
#        cursor.execute(sql, (name, about, session["username"], session["password"],))
#        db.commit()

#    sql = "select name, about from users where username=%s and password=%s"
#    cursor.execute(sql,(session["username"], session["password"]))
#    user1=cursor.fetchone()

#    return render_template("profile_edit.html", user=user, user1=user1)

# @app.route("/home", methods=["GET", "POST"])
# def home():
#    return redirect(url_for("dashboard"))

# @app.route("/add_a_post", methods=["GET", "POST"])
# def add_a_post():
#    cursor=db.cursor(dictionary=True, buffered=True)

#    if request.method == "POST":
#     file = request.files.get("photo")

#     if file and file.filename != "":
#        filename = secure_filename(file.filename)
#        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#        file.save(filepath)

#        sql = "insert into posts (username, photo) values(%s, %s)"
#        cursor.execute(sql, (session["username"], filename))
#        db.commit()

#    sql = "select photo from posts where username=%s order by id desc limit 1"
#    cursor.execute(sql, (session["username"],))
#    user=cursor.fetchone()

#    return render_template("add_a_post.html", user=user)

# @app.route("/profile_photos/<username>", methods=["GET", "POST"])
# def profile_photos(username):

#    cursor = db.cursor(dictionary=True, buffered=True)

#    # sql = "select photo from posts where username=%s"
#    # sql = """select photo from posts where username=%s and photo IS NOT NULL and photo != '' """
#    sql = """select id, photo from posts where username=%s and photo IS NOT NULL and photo != '' """
#    cursor.execute(sql,(username,))
#    users=cursor.fetchall()
  
#    return render_template("profile_photos.html", users=users, profile_owner=username, logged_user=session['username'])

# @app.route("/delete_photo", methods=["POST"])
# def delete_photo():
#    cursor = db.cursor(dictionary=True, buffered=True)

#    photo_id = request.form['photo_id']

#    sql = "delete from posts where id=%s"
#    cursor.execute(sql, (photo_id,))
#    db.commit()

#    # photo_id = request.form['photo_id']

#    # cursor.execute("select photo from posts where id=%s", (photo_id,))
#    # user = cursor.fetchone()

#    # if user and user['photo']:

#    #      path = "static/uploads/" + user['photo']

#    #      if os.path.exists(path):
#    #          os.remove(path)

#    # cursor.execute("delete from posts where id=%s", (photo_id,))
#    # db.commit()

#    return redirect('/profile_photos/' + session["username"])

# @app.route("/search", methods=["GET", "POST"])
# def search():

#    cursor=db.cursor(dictionary=True, buffered=True)

#    if request.method == "POST":
#       name=request.form.get("name")

#       if name:
#          sql = "select name, username from users where name=%s"
#          cursor.execute(sql, (name,))
#          user= cursor.fetchone()

#          if user:
#             # return redirect(f"/profile/{user['username']}/{user['name']}")
#             return redirect(url_for("profile", username=user["username"],))
         
#    return redirect("/dashboard")

# @app.route("/like/<int:post_id>", methods=["POST"])
# def like(post_id):
   
#    cursor=db.cursor(dictionary=True, buffered=True)

#    username=session["username"]
    
#    sql = "select * from likes where post_id=%s and username=%s"
#    cursor.execute(sql, (post_id, username,))
#    existing_like=cursor.fetchone()

#    if existing_like:
#       sql = "delete from likes where post_id=%s and username=%s"
#       cursor.execute(sql, (post_id, username,))
#       liked = False


#    else:
#       sql = "insert into likes(post_id, username) values(%s, %s)"
#       cursor.execute(sql, (post_id, username,))
#       liked = True

#    db.commit()

#    # return redirect("/dashboard")
#    # return redirect(url_for("dashboard"))

#    # get updated like count                                              # this part little unclear, related to java script
#    sql = "SELECT COUNT(*) AS total FROM likes WHERE post_id=%s"
#    cursor.execute(sql, (post_id,))
#    total_likes = cursor.fetchone()["total"]

#    return jsonify({
#         "liked": liked,
#         "total_likes": total_likes
#     })

# # @app.route("/comment/<int:comment_id>", methods=["GET", "POST"])
# # def comment(comment_id):

# #    # cursor = db.cursor(dictionary=True, buffered=True)

# #    # sql = "select comment from comments where comment_id=%s"
# #    # cursor.execute(sql, (comment_id,))

# #    # comments = cursor.fetchall()

# #    # return render_template("comment.html", comments=comments)
# #    # return render_template("comment.html")

# #    cursor = db.cursor(dictionary=True, buffered=True)

# #    if request.method == "POST":
# #     comment=request.form.get("comment")

# #    if comment:
# #       sql= " insert into comments(comment, comment_id) values(%s, %s)"
# #       cursor.execute(sql, (comment, comment_id,))
# #       db.commit()

# #    # sql = "select comment_id from comments where username=%s"
# #    # cursor.execute(sql, (session["username"],))
# #    # comments=cursor.fetchall()

# #    sql = "select comment from comments where comment_id=%s"
# #    cursor.execute(sql, (comment_id,))
# #    comments=cursor.fetchall()

# #    # return redirect(url_for("comment_save", comment_id=comments["comment_id"]),)
# #    return render_template("comment.html", comments=comments)


# @app.route("/comment_save/<int:comment_id>", methods=["GET", "POST"])
# def comment_save(comment_id):

#    cursor = db.cursor(dictionary=True, buffered=True)

#    if request.method == "POST":
#     comment=request.form.get("comment")


#     if comment:
#       sql= " insert into comments(comment_id, comment, username) values(%s, %s, %s)"
#       cursor.execute(sql, (comment_id, comment, session["username"],))
#       db.commit()

#       return redirect(url_for("comment_save", comment_id=comment_id))


#    # sql = "select comment, username, profile_photo, name from comments where comment_id=%s and username is not null and username != '' and profile_photo is not null and profile_photo != '' and name is not null and name != '' order by id desc "
#    sql = """
#    SELECT comments.comment,
#    comments.username,
#    users.profile_photo,
#    users.name

#    FROM comments

#    JOIN users
#    ON comments.username = users.username

#    WHERE comments.comment_id=%s

#    ORDER BY comments.id asc
#    """
#    cursor.execute(sql, (comment_id,))
#    comments=cursor.fetchall()

#    return render_template("comment.html", comments=comments)

# @app.route("/friends/<user>", methods=["GET", "POST"])
# def friends(user):

#    cursor=db.cursor(dictionary=True)

#    sql = "insert into friends(from_user, to_user) values(%s, %s)"
#    cursor.execute(sql,(user, session["username"],))

#    sql = "delete from friend_request where from_user=%s and to_user=%s"
#    cursor.execute(sql, (user, session["username"],))

#    db.commit()

#    # sql = """
#    #  SELECT 
#    #  users.username,
#    #  users.profile_photo,
#    #  users.name,
#    #  friends.*

#    #  FROM users
#    #  JOIN friends
#    #  ON users.username = friends.from_user

#    #  where friends.to_user=%s
#    #  """
#    # cursor.execute(sql, (session["username"],))
#    # datas2=cursor.fetchall()
#    # print(datas2)

#    # return render_template("friends.html", datas2=datas2)
#    # return redirect(url_for("profile", username=session["username"]))
#    return jsonify({"success" : True})

# @app.route("/friend_request/<to_user>", methods=["GET", "POST"])
# def friend_request(to_user):

#    cursor=db.cursor(dictionary=True)

#    sql = "select * from friend_request where to_user=%s and from_user=%s "
#    cursor.execute(sql, (to_user, session["username"],))
#    requests = cursor.fetchone()

#    if requests:
#       sql = "delete from friend_request where to_user=%s and from_user=%s"
#       cursor.execute(sql, (to_user, session["username"],))
      
#       db.commit()

#    else :
#       sql = "insert into friend_request(to_user, from_user) values(%s, %s)"
#       cursor.execute(sql, (to_user, session["username"],))
      
#    return redirect(url_for("profile", username=to_user))

# @app.route("/my_friends/<username>", methods=["GET", "POST"])
# def my_friends(username):

#    cursor=db.cursor(dictionary=True)

#    sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friends.*

#     FROM users
    
#     JOIN friends
#     ON users.username = friends.from_user
#     and friends.to_user = %s
#     """
#    cursor.execute(sql, (username,))
#    datas2=cursor.fetchall()

#    sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friends.*

#     FROM users
    
#     JOIN friends
#     ON users.username = friends.to_user
#     and friends.from_user = %s
#     """
#    cursor.execute(sql, (username,))
#    datas3=cursor.fetchall()
  
#    return render_template("my_friends.html", datas2=datas2, logged_in_user=session["username"], username=username, datas3=datas3) 


# @app.route("/notifications", methods=["GET", "POST"])
# def notifications():
   
#    cursor=db.cursor(dictionary=True, buffered=True)

#    sql = """
#     SELECT 
#     users.username,
#     users.profile_photo,
#     users.name,
#     friends.*

#     FROM users
    
#     JOIN friends
#     ON users.username = friends.to_user
#     and friends.from_user = %s
#     """
#    cursor.execute(sql, (session["username"],))
#    datas=cursor.fetchall()

#    return render_template("notifications.html", datas=datas)

# @app.route("/delete_request/<from_user>", methods=["GET", "POST"])
# def delete_request(from_user):

#    sql="delete  from friend_request where from_user=%s and to_user=%s"
#    cursor.execute(sql, (from_user, session["username"] ))
#    db.commit()

#    return redirect(url_for("profile", username=session["username"]))

# @app.route("/make_unfriend1/<from_user>", methods=["GET", "POST"])
# def make_unfriend1(from_user):

#    sql="delete from friends where from_user=%s and to_user=%s"
#    cursor.execute(sql, (from_user, session["username"]))
#    db.commit()

#    return redirect(url_for("my_friends", username=session["username"]))

# @app.route("/make_unfriend2/<to_user>", methods=["GET", "POST"])
# def make_unfriend2(to_user):

#    sql="delete from friends where from_user=%s and to_user=%s"
#    cursor.execute(sql, (session["username"], to_user))
#    db.commit()

#    return redirect(url_for("my_friends", username=session["username"]))

# @app.route("/deletePost/<int:postid>", methods=["GET", "POST"])
# def deletePost(postid):

#    cursor=db.cursor(dictionary=True)

#    sql="delete from posts where posts.id=%s and username=%s"
#    cursor.execute(sql, (postid, session["username"],))
#    db.commit()

#    return jsonify({"delete" : True})



# if __name__ == "__main__":
# #  app.run(use_reloader=False)
#  app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))