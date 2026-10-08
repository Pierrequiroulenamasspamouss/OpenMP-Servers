from flask import Flask
import threading
import logging

from config import Config
from routes.user import user_bp
from routes.game import game_bp
from routes.metrics import metrics_bp
from routes.sales import sales_bp
from routes.dashboard import dashboard_bp
from routes.chat import chat_bp
from utils.db import init_db, migrate_files_to_db

# Disable verbose logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def create_app(port):
    import os
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'html'))
    app = Flask(f"App_{port}", template_folder=template_dir)
    
    # Initialize DB
    init_db()
    # Migrate any legacy .json files
    migrate_files_to_db()
    
    # CRITICAL: Keep JSON order intact
    app.config['JSON_SORT_KEYS'] = False

    # Register Blueprints
    app.register_blueprint(user_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(chat_bp)

    from flask import request
    @app.before_request
    def log_request_info():
        print(f"[HTTP IN] {request.method} {request.url}", flush=True)

    return app

def run_server(port):
    app = create_app(port)
    from utils.db import start_backup_scheduler
    start_backup_scheduler()
    print(f">>> Server started on port {port}", flush=True)
    app.run(host=Config.HOST, port=port, debug=Config.DEBUG, threaded=True)

if __name__ == '__main__':
    import argparse
    from werkzeug.serving import make_server
    import os

    parser = argparse.ArgumentParser(description="Kampai Game Server")
    parser.add_argument("--public", action="store_true", help="Serve public URLs in dynamic config")
    parser.add_argument("--host", type=str, default=None, help="Host to bind")
    parser.add_argument("--port", type=int, default=None, help="Main port to bind")
    args, unknown = parser.parse_known_args()

    if args.public:
        Config.set_public(True)
    if args.host:
        Config.HOST = args.host
    if args.port:
        Config.PORT_MAIN = args.port

    mode_str = "PUBLIC (Production)" if Config.IS_PUBLIC else "LOCAL (Localhost)"
    print(f"==================================================", flush=True)
    print(f">>> Kampai Server Mode: {mode_str}", flush=True)
    print(f">>> Main Base URL:      {Config.get_base_url()}", flush=True)
    print(f">>> Secondary URL:      {Config.get_secondary_url()}", flush=True)
    print(f"==================================================", flush=True)

    # Secondary server thread on PORT_SECONDARY (44732)
    def run_secondary():
        app_sec = create_app(Config.PORT_SECONDARY)
        srv = make_server(Config.HOST, Config.PORT_SECONDARY, app_sec, threaded=True)
        print(f">>> Secondary Server started on port {Config.PORT_SECONDARY}", flush=True)
        srv.serve_forever()

    # Avoid running background threads in Werkzeug reloader parent process
    is_reloader_parent = Config.DEBUG and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'

    if not is_reloader_parent:
        t2 = threading.Thread(target=run_secondary, daemon=True)
        t2.start()
        print(f">>> Main Server started on port {Config.PORT_MAIN}", flush=True)
        from utils.db import start_backup_scheduler
        start_backup_scheduler()

    # Main server on PORT_MAIN (44733)
    app_main = create_app(Config.PORT_MAIN)
    app_main.run(host=Config.HOST, port=Config.PORT_MAIN, debug=Config.DEBUG, threaded=True, use_reloader=Config.DEBUG)


