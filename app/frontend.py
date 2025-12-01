import streamlit as st
import requests
import base64
import urllib.parse

# -----------------------
# Config
# -----------------------
API_BASE = "http://localhost:8000"  # change for production
st.set_page_config(page_title="Simple Social", layout="wide")

# -----------------------
# Session initialization
# -----------------------
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None
if 'last_token_check_failed' not in st.session_state:
    st.session_state.last_token_check_failed = False

# Try to restore token from URL query params (survives reloads)
query_params = st.experimental_get_query_params()
if not st.session_state.token and 'token' in query_params:
    st.session_state.token = query_params.get('token')[0]

def get_headers():
    """Get authorization headers with token"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

# If we have a token but no user object, attempt to fetch user info.
# This runs once on page load (or whenever session_state.token is set and user is None).
if st.session_state.token and st.session_state.user is None and not st.session_state.last_token_check_failed:
    try:
        user_response = requests.get(f"{API_BASE}/users/me", headers=get_headers(), timeout=5)
        if user_response.status_code == 200:
            st.session_state.user = user_response.json()
        else:
            # token invalid or expired -> clear token from state & URL
            st.session_state.token = None
            st.session_state.user = None
            st.experimental_set_query_params()  # clear token from URL
            st.session_state.last_token_check_failed = True
    except Exception:
        # network or backend down, avoid repeated failing attempts this run
        st.session_state.last_token_check_failed = True

# -----------------------
# Utility helpers
# -----------------------
def encode_text_for_overlay(text):
    """Encode text for ImageKit overlay - base64 then URL encode"""
    if not text:
        return ""
    base64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    return urllib.parse.quote(base64_text)

def create_transformed_url(original_url, transformation_params, caption=None):
    if caption:
        encoded_caption = encode_text_for_overlay(caption)
        text_overlay = f"l-text,ie-{encoded_caption},ly-N20,lx-20,fs-100,co-white,bg-000000A0,l-end"
        transformation_params = text_overlay

    if not transformation_params:
        return original_url

    parts = original_url.split("/")
    if len(parts) < 5:
        return original_url
    imagekit_id = parts[3]
    file_path = "/".join(parts[4:])
    base_url = "/".join(parts[:4])
    return f"{base_url}/tr:{transformation_params}/{file_path}"

# -----------------------
# Pages
# -----------------------
def login_page():
    st.title("🚀 Welcome to Simple Social")

    email = st.text_input("Email:")
    password = st.text_input("Password:", type="password")

    if email and password:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                login_data = {"username": email, "password": password}
                try:
                    response = requests.post(f"{API_BASE}/auth/jwt/login", data=login_data, timeout=8)
                except Exception:
                    st.error("Could not contact backend. Is the API running?")
                    return

                if response.status_code == 200:
                    token_data = response.json()
                    st.session_state.token = token_data["access_token"]

                    # Persist token to URL so it survives reloads (dev-only; not secure for production)
                    st.experimental_set_query_params(token=st.session_state.token)

                    # Immediately fetch the user
                    user_response = requests.get(f"{API_BASE}/users/me", headers=get_headers())
                    if user_response.status_code == 200:
                        st.session_state.user = user_response.json()
                        st.rerun()
                    else:
                        st.error("Failed to get user info")
                else:
                    st.error("Invalid email or password!")

        with col2:
            if st.button("Sign Up", type="secondary", use_container_width=True):
                signup_data = {"email": email, "password": password}
                try:
                    response = requests.post(f"{API_BASE}/auth/register", json=signup_data, timeout=8)
                except Exception:
                    st.error("Could not contact backend. Is the API running?")
                    return

                if response.status_code == 201:
                    st.success("Account created! Click Login now.")
                else:
                    try:
                        error_detail = response.json().get("detail", "Registration failed")
                    except Exception:
                        error_detail = "Registration failed"
                    st.error(f"Registration failed: {error_detail}")
    else:
        st.info("Enter your email and password above")

def upload_page():
    st.title("📸 Share Something")

    uploaded_file = st.file_uploader("Choose media", type=['png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov', 'mkv', 'webm'])
    caption = st.text_area("Caption:", placeholder="What's on your mind?")

    if uploaded_file and st.button("Share", type="primary"):
        with st.spinner("Uploading..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"caption": caption}
            try:
                response = requests.post(f"{API_BASE}/upload", files=files, data=data, headers=get_headers(), timeout=30)
            except Exception:
                st.error("Upload failed: cannot contact backend.")
                return

            if response.status_code == 200:
                st.success("Posted!")
                st.rerun()
            else:
                try:
                    err = response.json()
                except Exception:
                    err = response.text
                st.error(f"Upload failed! {err}")

def feed_page():
    st.title("🏠 Feed")

    try:
        response = requests.get(f"{API_BASE}/feed", headers=get_headers(), timeout=8)
    except Exception:
        st.error("Failed to contact backend. Is the API running?")
        return

    if response.status_code == 200:
        posts = response.json().get("posts", [])
        if not posts:
            st.info("No posts yet! Be the first to share something.")
            return

        for post in posts:
            st.markdown("---")
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{post.get('email','Unknown')}** • {post.get('created_at','')[:10]}")
            with col2:
                if post.get('is_owner', False):
                    if st.button("🗑️", key=f"delete_{post['id']}", help="Delete post"):
                        try:
                            resp = requests.delete(f"{API_BASE}/posts/{post['id']}", headers=get_headers(), timeout=8)
                        except Exception:
                            st.error("Failed to contact backend.")
                            continue

                        if resp.status_code == 200:
                            st.success("Post deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete post!")

            caption = post.get('caption', '')
            if post.get('file_type') == 'image':
                uniform_url = create_transformed_url(post.get('url', ''), "", caption)
                st.image(uniform_url, width=300)
            else:
                uniform_video_url = create_transformed_url(post.get('url', ''), "w-400,h-200,cm-pad_resize,bg-blurred")
                st.video(uniform_video_url, width=300)
                st.caption(caption)

            st.markdown("")

    else:
        st.error("Failed to load feed")

# -----------------------
# Main app logic
# -----------------------
if st.session_state.user is None:
    login_page()
else:
    # Sidebar navigation
    st.sidebar.title(f"👋 Hi {st.session_state.user['email']}!")

    if st.sidebar.button("Logout"):
        # Clear session & URL token
        st.session_state.user = None
        st.session_state.token = None
        st.experimental_set_query_params()  # clear query params (remove token)
        st.rerun()

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate:", ["🏠 Feed", "📸 Upload"])

    if page == "🏠 Feed":
        feed_page()
    else:
        upload_page()
