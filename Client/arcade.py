import base64
import copy
import logging
import os
import pickle
import random
import sys
import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
from io import BytesIO
from tkinter import filedialog as fd
from tkinter import messagebox as msgb

while True:
    try:
        import pyperclip as clipboard
        from PIL import Image, ImageChops, ImageDraw, ImageTk
        from plyer import notification as noti

        sys.path.append(
            os.path.join(
                os.path.abspath("."),
                "Client" if "Client" not in os.path.abspath(".") else "",
            )
        )

        from games.chess import Chess
        from games.monopoly import Monopoly
        from utilities.client_framework import Client
        from utilities.http_wrapper import Http
        from utilities.rules import Rules
        from utilities.theme import Theme

        break

    except ImportError as e:
        print(e)

        def load():
            cur = os.path.abspath(os.curdir)
            os.chdir(os.path.abspath(cur.replace("Client", "")))
            os.system(f"pip3 install -r requirements.txt")
            os.chdir(cur)
            loading.destroy()

        loading = tk.Tk()
        tk.Label(loading, text="Installing Required Modules...").pack()
        loading.after(100, load)
        loading.mainloop()


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


ASSET = resource_path(
    "assets" if os.path.exists("assets") else os.path.join("Client", "assets")
)
HOME_ASSETS = os.path.join(ASSET, "home_assets")
MONOPOLY_ASSETS = os.path.join(ASSET, "mnply_assets")
CHESS_ASSETS = os.path.join(ASSET, "chess_assets")

HTTP = Http("https://pramitpal.me/api")
CLIENT_ADDRESS = "pramitpal.me"
isWin = os.name == "nt"

REMEMBER_ME_FILE = (
    os.path.join(
        os.environ["USERPROFILE"],
        "AppData",
        "Local",
        "Arcade",
        "cred.dat",
    )
    if isWin
    else os.path.join(
        os.environ["HOME"],
        "Applications",
        "Arcade",
        "cred.dat",
    )
)

SETTINGS_FILE = (
    os.path.join(
        os.environ["USERPROFILE"],
        "AppData",
        "Local",
        "Arcade",
        "settings.dat",
    )
    if isWin
    else os.path.join(
        os.environ["HOME"],
        "Applications",
        "Arcade",
        "settings.dat",
    )
)

LOG_FILE = (
    os.path.join(
        os.environ["USERPROFILE"],
        "AppData",
        "Local",
        "Arcade",
        "log.log",
    )
    if isWin
    else os.path.join(
        os.environ["HOME"],
        "Applications",
        "Arcade",
        "log.log",
    )
)


logger = logging

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

if isWin:
    UPDATER_EXE = os.path.join(
        os.environ["USERPROFILE"], "AppData", "Local", "Arcade", "Updater.exe"
    )
else:
    logging.warning("I don't like your Operating System. Install Windows.")


class Rooms(dict):
    def __init__(self):
        super().__init__({"CHESS": {}, "MNPLY": {}})

    def __contains__(self, val):
        if val in self["CHESS"] or val in self["MNPLY"]:
            return True
        return False

    def initialize(self, game, rooms):
        self[game] = {}
        for room in rooms:
            self.add_room(game, room)

    def add_room(self, game, room):
        room["members"] = {i["puid"]: i for i in room["members"]}
        self[game][room["id"]] = room

    def remove_room(self, game, id):
        del self[game][id]

    def change_settings(self, rid, settings):
        key = "CHESS" if rid in self["CHESS"] else "MNPLY"
        self[key][rid]["settings"].update(settings)

    def get_rooms(self) -> dict:
        d = {}
        d.update(self["CHESS"])
        d.update(self["MNPLY"])
        return d

    def add_player(self, rid, player):
        key = "CHESS" if rid in self["CHESS"] else "MNPLY"
        self[key][rid]["members"][player["puid"]] = player

    def remove_player(self, rid, player):
        key = "CHESS" if rid in self["CHESS"] else "MNPLY"
        del self[key][rid]["members"][player]


class Arcade(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.lobby_frames = {"CHESS": None, "MNPLY": None}
        self.lobby_trees = {"CHESS": None, "MNPLY": None}
        self.room_frames = {"CHESS": None, "MNPLY": None}
        self.room_members = {"CHESS": None, "MNPLY": None}
        self.room_settings = {"CHESS": None, "MNPLY": None}
        self.leaderboard_details = {"chess": [], "monopoly": []}
        self.stats_details = {"chess": {}, "monopoly": {}}
        self.pfps = {"chess": {}, "monopoly": {}}
        self.updated_host_side = None

        self.current_room = None
        self.sent_time = time.perf_counter()
        self.refresh = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "refresh.png"))
        )
        self.copy_icon = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "copy.png"))
        )

        self.help_img = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "help.png")).resize(
                (20, 20), Image.Resampling.LANCZOS
            )
        )
        # GUI Initializing
        self.screen_width = int(0.9 * self.winfo_screenwidth())
        self.screen_height = int(self.screen_width / 1.9)
        self.x_coord = self.winfo_screenwidth() // 2 - self.screen_width // 2
        self.y_coord = (self.winfo_screenheight() - 70) // 2 - self.screen_height // 2

        self.title("Arcade")
        self.geometry(
            f"{self.screen_width//2}x{self.screen_height}+{self.x_coord+self.screen_width//4}+{self.y_coord}"
        )
        self.protocol("WM_DELETE_WINDOW", self.exit)
        self.iconbitmap(os.path.join(HOME_ASSETS, "icon.ico"))
        self.minsize(self.screen_width // 2, self.screen_height)

        self.current_room = None

    # region # Initialising

    def initialize(self, name, token):
        self.geometry(
            f"{self.screen_width}x{self.screen_height}+{self.x_coord}+{self.y_coord}"
        )
        self.minsize(self.screen_width, self.screen_height)
        self.name = name
        self.token = token
        self.rooms = Rooms()

        self.current_room = None

        try:
            self.cobj = Client((CLIENT_ADDRESS, 6969), self.event_handler, token)
            self.cobj.send((self.name,))
        except ConnectionRefusedError as e:
            logging.exception(e)
            HTTP.logout()
            self.destroy()
            msgb.showerror(
                "Try Again Later",
                "Unable to connect to the Server at the moment, please try again later!\nThings you can do:\n1. Check your network connection\n2. Restart your system\n3. If this issue persists, wait for sometime. The server might be down, We are working on it!",
                master=root,
            )
            quit()

        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.place(relx=0, rely=0, anchor="nw", relheight=1, relwidth=1)
        self.main_notebook.enable_traversal()

        self.chess_frame = tk.Frame(self.main_notebook)
        self.chess_frame.place(relx=0, rely=0, relheight=1, relwidth=1, anchor="nw")
        self.main_notebook.add(self.chess_frame, text="Chess")
        self.chess_icon = ImageTk.PhotoImage(
            Image.open(os.path.join(CHESS_ASSETS, "icon.ico")).resize(
                (40, 40), Image.Resampling.LANCZOS
            )
        )
        tk.Label(
            self.chess_frame,
            image=self.chess_icon,
            text=" CHESS",
            font=("stencil", 40),
            fg="#4656b4",
            compound="left",
        ).place(relx=0.5, rely=0.0375, anchor="center")
        self.leaderboard("chess")
        self.stats("chess")
        self.join_create("CHESS")

        self.monopoly_frame = tk.Frame(self.main_notebook)
        self.monopoly_frame.place(relx=0, rely=0, relheight=1, relwidth=1, anchor="nw")
        self.main_notebook.add(self.monopoly_frame, text="Monopoly")
        self.mono_icon = ImageTk.PhotoImage(
            Image.open(os.path.join(MONOPOLY_ASSETS, "icon.ico")).resize(
                (45, 45), Image.Resampling.LANCZOS
            )
        )
        tk.Label(
            self.monopoly_frame,
            image=self.mono_icon,
            text=" MONOPOLY",
            font=("stencil", 30),
            fg="#4656b4",
            compound="left",
        ).place(relx=0.5, rely=0.0375, anchor="center")
        self.leaderboard("monopoly")
        self.stats("monopoly")
        self.join_create("MNPLY")

        tk.Button(
            self,
            image=self.help_img,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: Rules(self, "Arcade"),
        ).place(relx=0.999, rely=0.001, anchor="ne")

        with open(SETTINGS_FILE, "rb") as f:
            d = pickle.load(f)
            self.main_notebook.select(d["DEFAULT_GAME"])

        self.my_pfp = Arcade.get_pfp(self.name, (40, 40))

        self.acc_button = tk.Button(
            self,
            image=self.my_pfp,
            text=f" {self.name} ▾",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            font=("arial black", 14),
            compound="left",
            command=self.account_tab,
        )
        self.acc_button.place(relx=0.99, rely=0.07, anchor="e")
        self.acc_frame = ttk.Frame()
        self.acc_frame.destroy()

    def start_arcade(self):
        root.withdraw()
        self.logo = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "logo.png")).resize(
                (self.screen_width // 2, self.screen_width // 4),
                Image.Resampling.LANCZOS,
            )
        )
        tk.Label(self, image=self.logo, bg=self.cget("bg")).place(
            relx=0.5, rely=0.3, anchor="center", relheight=0.8, relwidth=1
        )
        Login(
            self, self.initialize, remember_login=os.path.exists(REMEMBER_ME_FILE)
        ).place(relx=0.5, rely=0.6, relheight=0.4, relwidth=1, anchor="n")

    def join_create(self, game):
        parent = self.chess_frame if game == "CHESS" else self.monopoly_frame

        join_button = ttk.Button(
            parent,
            text="Join A Room",
            style="20.TButton",
            command=lambda: self.join_lobby(game),
        )
        join_button.place(relx=0.5, rely=0.4, anchor="center")

        create_button = ttk.Button(
            parent,
            text="Create A Room",
            style="20.TButton",
            command=lambda: self.create_room(game),
        )
        create_button.place(relx=0.5, rely=0.6, anchor="center")

    @staticmethod
    def get_active_window():
        if isWin:
            from ctypes import create_unicode_buffer, windll

            hWnd = windll.user32.GetForegroundWindow()
            length = windll.user32.GetWindowTextLengthW(hWnd)
            buf = create_unicode_buffer(length + 1)
            windll.user32.GetWindowTextW(hWnd, buf, length + 1)
            return buf.value if buf.value else None
        else:
            return None

    # endregion

    # region # Event Handling

    def event_handler(self, msg):
        try:
            dest = msg[0]
            logging.info(f"Recv: {msg}")
            room = None
            if dest == "NAME":
                self.me = msg[1]
            elif dest == "GAME":
                if msg[1] == "SESSION_EXP":
                    self.show_message(
                        "Session Expired",
                        "You have been inactive for too long! Please Re-login to Continue!",
                        type="error",
                    )
                    self.cobj.close()
                    self.log_out(True)
            elif dest in ["CHESS", "MNPLY"]:
                if msg[1] == "INIT":
                    self.rooms.initialize(dest, msg[2])
                elif msg[1] == "JOIN_ERR":
                    self.show_message(
                        "Invalid ID",
                        "The Room you're trying to join is invalid! Please Enter the Correct Room ID.",
                        "warning",
                        4000,
                    )
                    self.join_pvt_entry.delete(0, "end")
                elif msg[1] == "ROOM":
                    room = msg[3]
                    if msg[2] == "ADD":
                        self.rooms.add_room(dest, room)
                    elif msg[2] == "REMOVE":
                        self.rooms.remove_room(dest, msg[3])
                elif msg[1] == "PLAYER":
                    if msg[2] == "ADD":
                        self.rooms.add_player(msg[4], msg[3])
                    elif msg[2] == "REMOVE":
                        self.rooms.remove_player(msg[4], msg[3])
                elif msg[1] == "SETTINGS":
                    self.rooms.change_settings(msg[3], msg[2])
                self.update_lobby(dest)  # TODO Settings GUI in Lobby

            elif dest == "ROOM":
                if msg[1] == "ADD":
                    self.rooms.add_room(msg[2], msg[3])
                    self.join_room(msg[3]["id"], msg[2])
                elif msg[1] == "REJECT":
                    self.join_lobby(msg[2])
                    self.show_message(
                        "Room Full",
                        "The Room you tried to Join is full and can't accept any more players!",
                        timeout=4000,
                        type="warning",
                    )

            elif dest == self.current_room:
                game = "CHESS" if dest in self.rooms["CHESS"] else "MNPLY"
                if msg[1] == "PLAYER":
                    if msg[2] == "ADD":
                        self.rooms.add_player(dest, msg[3])
                        if self.get_active_window() != "Arcade" and isWin:
                            noti.notify(
                                message=f"{msg[3]['name']} has joined the room!",
                                app_name="Arcade",
                                timeout=5,
                            )
                    elif msg[2] == "REMOVE":
                        if self.get_active_window() != "Arcade" and isWin:
                            noti.notify(
                                message=f"{msg[3]['name']} has left the room!",
                                app_name="Arcade",
                                timeout=5,
                            )
                        self.rooms.remove_player(dest, msg[3])
                    self.update_room(self.rooms[game][dest])

                elif msg[1] == "SETTINGS":
                    self.rooms.change_settings(dest, msg[2])
                    self.update_room(self.rooms[game][dest])

                elif msg[1] == "ROOM":
                    self.room_frames[game].destroy()
                    self.room_frames[game] = None
                    if msg[2] == "REMOVE":
                        if isWin:
                            noti.notify(
                                message=f"The Host Left the Room!",
                                app_name="Arcade",
                                timeout=5,
                            )
                        self.rooms.remove_room(game, dest)
                        self.current_room = None
                    elif msg[2] == "START":
                        self.withdraw()
                        if game == "CHESS":
                            self.game = Chess(
                                logging.getLogger(),
                                msg[3],
                                lambda move: self.send((dest, "MSG", move)),
                                HTTP,
                                back=self.end_game,
                                theme=theme,
                            )
                        elif game == "MNPLY":
                            details = msg[3]
                            self.game = Monopoly(
                                logging.getLogger(),
                                details[0],
                                details[1],
                                lambda msg: self.send((dest, *msg)),
                                HTTP,
                                details[2],
                                back=self.end_game,
                                theme=theme,
                            )

                elif msg[1] == "MSG":
                    self.game.event_handler(msg[2])
        except tk.TclError as e1:
            logging.warning(f"TclError: {e1}")
        except Exception as e:
            logging.exception(e)
            HTTP.logout()
            self.destroy()
            if msgb.askokcancel(
                "ERROR",
                """An Error Occured! Please Restart to Continue!
Click 'Ok' if you'd like to view the crash logs! Feel free to report any bugs you find!""",
                icon=msgb.ERROR,
                master=root,
            ):
                os.startfile(LOG_FILE)
            root.destroy()

    def send(self, msg):
        time_gap = 0.1
        new_time = time.perf_counter()
        if (self.sent_time + time_gap) > new_time:
            t = threading.Thread(
                target=self.queue_send,
                args=(msg, (self.sent_time + time_gap - new_time)),
            )
            t.daemon = True
            t.start()
        else:
            self.queue_send(msg, None)

    def queue_send(self, msg, t):
        if t != None:
            self.sent_time = self.sent_time + 0.1
            time.sleep(t)
        else:
            self.sent_time = time.perf_counter() + 0.1
        try:
            self.cobj.send(msg)
            logging.info(f"Sent: {msg}")
        except Exception as e:
            logging.exception(e)
            self.show_message(
                "Connection Lost!",
                "You have been disconnected from the server! Please Restart to Continue!",
                type="error",
            )
            self.cobj.close()
            HTTP.logout()
            root.destroy()
            quit()

    # endregion

    # region # Account Tab

    def account_tab(self):
        if self.acc_frame.winfo_exists():
            self.unbind("<Button-1>")
            self.acc_frame.destroy()
        else:
            try:
                self.change_frame.destroy()
            except:
                pass

            def clicked(e):
                if self.acc_frame.winfo_containing(e.x_root, e.y_root) not in [
                    self.log_out_button,
                    self.change_pass_button,
                    self.change_pfp_button,
                    self.check_updates_button,
                    self.acc_frame,
                    self.acc_button,
                    self.theme_button,
                    self.ch_rb,
                    self.mo_rb,
                ]:
                    self.acc_frame.destroy()
                    self.unbind("<Button-1>")

            self.bind("<Button-1>", clicked)
            self.acc_frame = ttk.Frame(self, style="Card.TFrame", padding=4)
            self.acc_frame.place(relx=0.99, rely=0.1, anchor="ne")

            self.log_out_button = ttk.Button(
                self.acc_frame, text="Log Out", style="12.TButton", command=self.log_out
            )
            self.log_out_button.grid(
                row=0,
                column=0,
                columnspan=2,
                pady=2,
                sticky="nsew",
            )

            self.change_pass_button = ttk.Button(
                self.acc_frame,
                text="Change Password",
                style="12.TButton",
                command=self.change_password,
            )
            self.change_pass_button.grid(
                row=1, column=0, columnspan=2, sticky="nsew", pady=2
            )

            self.change_pfp_button = ttk.Button(
                self.acc_frame,
                text="Change Picture",
                style="12.TButton",
                command=self.change_pfp,
            )
            self.change_pfp_button.grid(
                row=2, column=0, columnspan=2, sticky="nsew", pady=2
            )

            self.check_updates_button = ttk.Button(
                self.acc_frame,
                text="Check for Updates",
                style="12.TButton",
                command=lambda: os.startfile(UPDATER_EXE),
            )
            self.check_updates_button.grid(
                row=3, column=0, columnspan=2, sticky="nsew", pady=2
            )

            theme_var = tk.StringVar(value=theme.curr_theme())

            tk.Label(self.acc_frame, text="Dark Mode", font=("rockwell", 14)).grid(
                row=4, column=0, sticky="e", pady=2, padx=6
            )
            self.theme_button = ttk.Checkbutton(
                self.acc_frame,
                style="Switch.TCheckbutton",
                variable=theme_var,
                onvalue="dark",
                offvalue="light",
                command=theme.toggle_theme,
            )
            self.theme_button.grid(row=4, column=1, sticky="e", pady=2)

            ttk.Separator(self.acc_frame, orient="horizontal").grid(
                row=5, column=0, columnspan=2, sticky="nsew", pady=2
            )

            tk.Label(
                self.acc_frame, text="Default Game", font=("rockwell", 12, "underline")
            ).grid(row=6, column=0, columnspan=2, sticky="nsew")

            default = tk.IntVar()

            with open(SETTINGS_FILE, "rb") as f:
                d = pickle.load(f)
                default.set(d["DEFAULT_GAME"])

            def default_game():
                with open(SETTINGS_FILE, "rb+") as f:
                    d = pickle.load(f)
                    d["DEFAULT_GAME"] = default.get()
                    f.seek(0)
                    pickle.dump(d, f)

            self.ch_rb = ttk.Radiobutton(
                self.acc_frame,
                text="Chess",
                variable=default,
                value=0,
                command=default_game,
            )
            self.ch_rb.grid(row=7, column=0, columnspan=2, sticky="nsew")
            self.mo_rb = ttk.Radiobutton(
                self.acc_frame,
                text="Monopoly",
                variable=default,
                value=1,
                command=default_game,
            )
            self.mo_rb.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=2)

    def change_password(self):
        self.acc_frame.destroy()
        self.change_frame = ttk.Frame(self, style="Card.TFrame", padding=4)
        self.change_frame.place(
            relx=0.99, rely=0.1, relheight=0.3, relwidth=0.25, anchor="ne"
        )
        self.pwd = tk.StringVar()
        self.confpwd = tk.StringVar()
        tk.Button(
            self.change_frame,
            text="← Cancel",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=self.change_frame.destroy,
        ).place(relx=0.01, rely=0.01, anchor="nw")

        self.change_frame.bind("<Escape>", lambda a: self.change_frame.destroy())
        tk.Label(self.change_frame, text="New Password: ").place(
            relx=0.49, rely=0.25, anchor="e"
        )
        self.pwdentry = ttk.Entry(self.change_frame, textvariable=self.pwd, show="*")
        self.pass_hidden = True
        self.pwdentry.place(relx=0.5, rely=0.25, relwidth=0.275, anchor="w")
        self.pwdentry.focus_set()
        tk.Label(self.change_frame, text="Confirm Password: ").place(
            relx=0.49, rely=0.4, anchor="e"
        )
        self.confpwdentry = ttk.Entry(
            self.change_frame, textvariable=self.confpwd, show="*"
        )
        self.conf_pass_hidden = True
        self.confpwdentry.place(relx=0.5, rely=0.4, relwidth=0.275, anchor="w")

        self.pwdentry.bind("<Return>", lambda a: self.confpwdentry.focus_set())
        self.confpwdentry.bind("<Return>", lambda a: self.confpwdentry.focus_set())

        def chng_pass():
            pwd = self.pwd.get().strip()
            confpwd = self.confpwd.get().strip()

            self.confpwdentry.delete(0, tk.END)
            prompts = {
                "length": "Atleast 4 Characters in Total",
                "space": "No Spaces",
            }
            missing = Register.check_pass(pwd)

            msg = ""
            if not pwd:
                self.pwdentry.delete(0, tk.END)
                msg = "Enter Password"
                prompt(msg)
            elif pwd and not confpwd:
                msg = "Confirm Password"
                prompt(msg)
            elif missing:
                self.pwdentry.delete(0, tk.END)
                msg = "Password should have:"
                for i in missing:
                    msg += "\n" + prompts[i]
                prompt(msg)
            elif confpwd != pwd:
                msg = "Password does not match"
                prompt(msg)
            else:
                if HTTP.change_password(pwd.strip()):
                    msg = "Confirming and Logging you out..."
                    prompt(msg)
                    try:
                        os.remove(REMEMBER_ME_FILE)
                    except FileNotFoundError:
                        pass
                    self.after(2000, self.log_out)
                else:
                    self.pwdentry.delete(0, tk.END)
                    msg = "ERROR"
                    prompt(msg)

        def prompt(msg):
            try:
                destroyprompt()
                self.notifc += 1
                color = "red"
                if msg.startswith("Confirming"):
                    color = "green"
                self.notif = (
                    tk.Label(self.change_frame, text=msg, fg=color),
                    self.notifc,
                )
                self.notif[0].place(
                    relx=0.5, rely=0.55 if "\n" not in msg else 0.7, anchor="center"
                )
                self.after(5000, destroyprompt)

            except:
                pass

        def destroyprompt():
            if self.notif and self.notif[1] == self.notifc:
                self.notif[0].destroy()
                self.notif = None

        self.change_button = ttk.Button(
            self.change_frame,
            text="CHANGE",
            style="12.TButton",
            command=chng_pass,
        )
        self.change_button.place(relx=0.5, rely=0.7, anchor="center")

        self.show_password = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "show_password.png")).resize(
                (20, 15), Image.Resampling.LANCZOS
            )
        )

        self.hide_password = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "hide_password.png")).resize(
                (20, 15), Image.Resampling.LANCZOS
            )
        )

        self.show_hide_pass = tk.Button(
            self.change_frame,
            image=self.show_password,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: toggle_hide_password(False),
        )
        self.show_hide_conf_pass = tk.Button(
            self.change_frame,
            image=self.show_password,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: toggle_hide_password(True),
        )
        self.show_hide_pass.place(relx=0.8, rely=0.25, anchor="w")
        self.show_hide_conf_pass.place(relx=0.8, rely=0.4, anchor="w")

        def toggle_hide_password(conf):
            if conf:
                if self.conf_pass_hidden:
                    self.confpwdentry.config(show="")
                    self.show_hide_conf_pass.config(image=self.hide_password)
                else:
                    self.confpwdentry.config(show="*")
                    self.show_hide_conf_pass.config(image=self.show_password)
                self.conf_pass_hidden = not self.conf_pass_hidden
            else:
                if self.pass_hidden:
                    self.pwdentry.config(show="")
                    self.show_hide_pass.config(image=self.hide_password)
                else:
                    self.pwdentry.config(show="*")
                    self.show_hide_pass.config(image=self.show_password)
                self.pass_hidden = not self.pass_hidden

        self.confpwdentry.bind("<Return>", lambda a: chng_pass())

        self.notif = None
        self.notifc = 0

    def change_pfp(self):
        self.acc_frame.destroy()
        self.pfp_path = os.path.join(HOME_ASSETS, "cached_pfp", self.name + ".png")
        self.change_frame = ttk.Frame(self, style="Card.TFrame", padding=4)
        self.change_frame.place(
            relx=0.99, rely=0.1, relheight=0.3, relwidth=0.25, anchor="ne"
        )
        tk.Button(
            self.change_frame,
            text="← Cancel",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=self.change_frame.destroy,
        ).place(relx=0.01, rely=0.01, anchor="nw")
        self.select_pfp()

    def select_pfp(self):
        self.pfp_image = ImageTk.PhotoImage(
            Arcade.circle_PIL_Image(Image.open(self.pfp_path), (100, 100))
        )
        tk.Label(self.change_frame, image=self.pfp_image).place(
            relx=0.5, rely=0.3, anchor="center"
        )
        self.remove_image = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "remove.png")).resize(
                (32, 32),
                Image.Resampling.LANCZOS,
            )
        )

        def choose():
            n = fd.askopenfilename(
                title="Choose a Profile Picture",
                initialdir=r"%userprofile%",
                filetypes=(("Image Files", "*.jpg *.png *.webp *.gif *.jpeg"),),
            )
            self.pfp_path = n if n else self.pfp_path
            self.select_pfp()

        def set_default():
            self.pfp_path = os.path.join(HOME_ASSETS, "default_pfp.png")
            self.select_pfp()

        self.remove_button = tk.Button(
            self.change_frame,
            image=self.remove_image,
            cursor="hand2",
            border=0,
            highlightthickness=0,
            command=set_default,
        )
        if self.pfp_path == os.path.join(HOME_ASSETS, "default_pfp.png"):
            self.remove_button.destroy()
        else:
            self.remove_button.place(relx=0.8, rely=0.45, anchor="center")

        self.choose_button = ttk.Button(
            self.change_frame,
            text="Upload Picture",
            style="12.TButton",
            command=choose,
        )
        self.choose_button.place(relx=0.5, rely=0.625, anchor="center")

        def confirm_change():
            HTTP.change_pfp(Arcade.pfp_send(self.pfp_path))
            self.change_frame.destroy()
            self.my_pfp = Arcade.get_pfp(self.name, force=True)
            self.acc_button.configure(image=self.my_pfp)

            if self.current_room:
                self.update_room(self.rooms.get_rooms()[self.current_room])

        self.confirm_button = ttk.Button(
            self.change_frame,
            text="Confirm",
            style="12.TButton",
            command=confirm_change,
        )

        if self.pfp_path == os.path.join(HOME_ASSETS, "cached_pfp", self.name + ".png"):
            self.confirm_button.destroy()
        else:
            self.confirm_button.place(relx=0.5, rely=0.9, anchor="center")

    def log_out(self, session=False):
        if not session:
            self.send(("GAME", "LEAVE"))
            try:
                os.remove(REMEMBER_ME_FILE)
            except FileNotFoundError:
                pass
        HTTP.logout()
        self.main_notebook.destroy()
        self.acc_button.destroy()
        self.acc_frame.destroy()
        try:
            self.change_frame.destroy()
        except:
            pass

        self.screen_width = int(0.9 * self.winfo_screenwidth())
        self.screen_height = int(self.screen_width / 1.9)
        self.x_coord = self.winfo_screenwidth() // 2 - self.screen_width // 2
        self.y_coord = (self.winfo_screenheight() - 70) // 2 - self.screen_height // 2
        self.minsize(self.screen_width // 2, self.screen_height)
        self.geometry(
            f"{self.screen_width//2}x{self.screen_height}+{self.x_coord+self.screen_width//4}+{self.y_coord}"
        )
        self.protocol("WM_DELETE_WINDOW", self.exit)

        tk.Label(self, image=self.logo, bg=self.cget("bg")).place(
            relx=0.5, rely=0.3, anchor="center", relheight=0.6, relwidth=1
        )
        Login(
            self, self.initialize, remember_login=os.path.exists(REMEMBER_ME_FILE)
        ).place(relx=0.5, rely=0.6, relheight=0.4, relwidth=1, anchor="n")

    # endregion

    # region # Profile Picture

    @staticmethod
    def pfp_send(path):
        im = Image.open(path)
        im = im.crop(
            (
                (im.size[0] - min(im.size)) // 2,
                (im.size[1] - min(im.size)) // 2,
                (im.size[0] + min(im.size)) // 2,
                (im.size[1] + min(im.size)) // 2,
            )
        ).resize((256, 256), Image.Resampling.LANCZOS)
        im.save(os.path.join(HOME_ASSETS, "temp.png"), optimize=True)
        with open(os.path.join(HOME_ASSETS, "temp.png"), "rb") as f:
            a = base64.b64encode(f.read()).decode("latin1")
        os.remove(os.path.join(HOME_ASSETS, "temp.png"))
        return a

    @staticmethod
    def pfp_make(img):
        try:
            b = base64.b64decode(img.encode("latin1"))
            c = Image.open(BytesIO(b))
            return c
        except Exception as e:
            logging.exception(f"Couldn't Access Profile Picture\n{e}")
            return Image.open(os.path.join(HOME_ASSETS, "default_pfp.png"))

    @staticmethod
    def get_pfp(name, resize=(32, 32), force=False):
        if (
            not os.path.isfile(os.path.join(HOME_ASSETS, "cached_pfp", name + ".png"))
            or force
        ):
            Arcade.circle_PIL_Image(Arcade.pfp_make(HTTP.fetch_pfp(name))).save(
                os.path.join(HOME_ASSETS, "cached_pfp", name + ".png")
            )
        return ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "cached_pfp", name + ".png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )

    @staticmethod
    def circle_PIL_Image(pil_img: Image.Image, resize=(256, 256)):
        im = pil_img.convert("RGBA")
        im = im.crop(
            (
                (im.size[0] - min(im.size)) // 2,
                (im.size[1] - min(im.size)) // 2,
                (im.size[0] + min(im.size)) // 2,
                (im.size[1] + min(im.size)) // 2,
            )
        ).resize(resize, Image.Resampling.LANCZOS)
        bigsize = (im.size[0] * 10, im.size[1] * 10)

        mask = Image.new("L", bigsize, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + bigsize, fill=255)
        mask = mask.resize(im.size, Image.Resampling.LANCZOS)
        mask = ImageChops.darker(
            mask,
            im.split()[-1],
        )
        im.putalpha(mask)

        a = im.resize(bigsize)
        ImageDraw.Draw(a).ellipse((0, 0) + (bigsize), outline=(0, 0, 0), width=15)
        a = a.resize(im.size, Image.Resampling.LANCZOS)
        im.paste(a)

        return im

    # endregion

    def show_message(self, title, message, type="info", timeout=0):
        self.mbwin = tk.Tk()
        self.mbwin.withdraw()
        try:
            if timeout:
                self.mbwin.after(timeout, self.mbwin.destroy)
            if type == "info":
                msgb.showinfo(title, message, master=self.mbwin)
            elif type == "warning":
                msgb.showwarning(title, message, master=self.mbwin)
            elif type == "error":
                msgb.showerror(title, message, master=self.mbwin)
            elif type == "okcancel":
                okcancel = msgb.askokcancel(title, message, master=self.mbwin)
                return okcancel
            elif type == "yesno":
                yesno = msgb.askyesno(title, message, master=self.mbwin)
                return yesno
        except Exception as e:
            logging.exception(e)

    # region # Lobby

    def join_lobby(self, game):
        parent = self.chess_frame if game == "CHESS" else self.monopoly_frame
        self.lobby_frames[game] = ttk.Frame(parent, style="Card.TFrame")
        self.lobby_frames[game].place(
            relx=0.5, rely=0.525, anchor="center", relwidth=0.33, relheight=0.9
        )
        frame = self.lobby_frames[game]

        tk.Button(
            frame,
            text="← BACK",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: self.leave_lobby(game),
        ).place(relx=0.01, rely=0.01, anchor="nw")

        self.bind("<Escape>", lambda a: self.leave_lobby(game))

        scroll = ttk.Scrollbar(frame, orient="vertical")
        scroll.place(relx=0.9975, rely=0.075, anchor="ne", relheight=0.75)
        tk.Label(frame, text="Select A Room", font=("rockwell", 13, "underline")).place(
            relx=0.5, rely=0.025, anchor="center"
        )

        self.lobby_trees[game] = ttk.Treeview(
            frame, columns=("Room", "Host", "Players"), yscrollcommand=scroll.set
        )
        tree = self.lobby_trees[game]
        tree.place(relx=0.49, rely=0.075, anchor="n", relheight=0.75, relwidth=0.96)

        def join_some_room():
            clear()
            if self.join_pvt_entry.get():
                self.join_selected_room([self.join_pvt_entry.get().upper()], game)

        self.join_select_room_button = ttk.Button(
            frame,
            text="Join",
            style="13.TButton",
            command=join_some_room,
        )
        self.join_select_room_button.place(relx=0.51, rely=0.99, anchor="s")

        scroll.configure(command=tree.yview)
        tree.column(
            "#0",
            width=10,
        )
        tree.bind("<Return>", lambda e: join_some_room())

        tree.column(
            "Room",
            width=self.screen_width // 10,
            anchor="center",
            minwidth=self.screen_width // 10,
        )
        tree.column(
            "Host",
            width=self.screen_width // 10,
            anchor="center",
            minwidth=self.screen_width // 10,
        )
        tree.column(
            "Players",
            width=self.screen_width // 10,
            anchor="center",
            minwidth=self.screen_width // 10,
        )

        tree.heading("#0", text="")
        tree.heading("Room", text="Room No.", anchor="center")
        tree.heading("Host", text="Host", anchor="center")
        tree.heading("Players", text="No. of Players", anchor="center")

        def no_special(e):
            if e.isalnum() and len(e) <= 6 or not e:
                return True
            else:
                return False

        def clear():
            e = self.join_pvt_entry.get()
            if not (e.isalnum() and len(e) == 6):
                self.join_pvt_entry.delete(0, "end")

        def caps():
            a = self.join_pvt_entry.get().upper()
            self.join_pvt_entry.delete(0, "end")
            self.join_pvt_entry.insert(0, a)

        self.pvt_id = tk.StringVar()
        self.join_pvt_entry = ttk.Entry(
            frame,
            textvariable=self.pvt_id,
            validate="key",
            validatecommand=(
                self.register(no_special),
                "%P",
            ),
        )
        tk.Label(frame, text="or Enter Room ID:", font=("rockwell", 13)).place(
            relx=0.55, rely=0.85, anchor="e"
        )

        def treeview_click(e):
            self.join_pvt_entry.delete(0, "end")
            self.join_pvt_entry.insert(0, tree.focus())

        tree.bind("<<TreeviewSelect>>", treeview_click)
        self.join_pvt_entry.place(relx=0.57, rely=0.85, relwidth=0.2, anchor="w")
        self.join_pvt_entry.focus_set()
        self.join_pvt_entry.bind("<Return>", lambda e: join_some_room())
        self.join_pvt_entry.bind("<KeyRelease>", lambda e: caps())
        self.join_pvt_entry.bind("<FocusOut>", lambda e: clear())

        self.send(("0", "JOIN", game.upper()))

    def update_lobby(self, game):
        for item in self.lobby_trees[game].get_children():
            self.lobby_trees[game].delete(item)
        if self.rooms[game]:
            for id, room in self.rooms[game].items():
                if len(room["members"]) >= room["settings"]["MAX_PLAYERS"]:
                    continue
                hostname = room["members"][room["host"]]["name"]
                self.lobby_trees[game].insert(
                    parent="",
                    index="end",
                    iid=id,
                    text="",
                    values=(id, hostname, len(room["members"])),
                )

    def leave_lobby(self, game, frame_preserve=False):
        if not frame_preserve:
            self.lobby_frames[game].destroy()
            self.lobby_frames[game] = None
        self.unbind("<Escape>")
        self.send(("0", "LEAVE", game.upper()))

    # endregion

    # region # Room

    def join_selected_room(self, room, game):
        if len(room) != 1:
            return
        if self.current_room:
            if self.show_message(
                "Room Already Joined!",
                "Do you want to leave the previous room and join here?",
                "yesno",
            ):
                self.leave_room(self.current_room, confirm=False)
            else:
                return

        self.leave_lobby(game, frame_preserve=True)
        self.send((game, "JOIN", room[0]))

    def create_room(self, game):
        settings = {}
        if self.current_room:
            if self.show_message(
                "Room Already Joined!",
                "Do you want to leave the previous room and create a new one?",
                "yesno",
            ):
                self.leave_room(self.current_room, confirm=False)
            else:
                return
        if game == "CHESS":
            settings = {
                "STATUS": "PRIVATE",
                "MAX_PLAYERS": 2,
                "TIME": 600,
                "ADD_TIME": 5,
                "HOST_SIDE": random.choice(("BLACK", "WHITE")),
            }
        if game == "MNPLY":
            settings = {
                "STATUS": "PRIVATE",
                "MAX_PLAYERS": 4,
            }
        self.send((game, "CREATE", settings))

    def join_room(self, room, game=None):
        if room in self.rooms:
            game = "CHESS" if room in self.rooms["CHESS"] else "MNPLY"

        if self.lobby_frames[game]:
            self.lobby_frames[game].destroy()
            self.lobby_frames[game] = None

        room = self.rooms[game][room]
        self.current_room = room["id"]
        parent = self.chess_frame if game == "CHESS" else self.monopoly_frame
        hostname = (
            "You" if self.me == room["host"] else room["members"][room["host"]]["name"]
        )

        self.room_frames[game] = ttk.Frame(parent, style="Card.TFrame")
        frame: ttk.Frame = self.room_frames[game]
        frame.place(relx=0.5, rely=0.525, anchor="center", relwidth=0.33, relheight=0.9)

        tk.Button(
            frame,
            text="← BACK",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: self.leave_room(
                self.current_room, game, delete=hostname == "You"
            ),
        ).place(relx=0.01, rely=0.01, anchor="nw")

        self.bind(
            "<Escape>",
            lambda a: self.leave_room(
                self.current_room, game, delete=hostname == "You"
            ),
        )

        tk.Label(
            frame,
            text=f"Room ID: {self.current_room}",
            font=("rockwell", 13),
        ).place(relx=0.5, rely=0.05, anchor="center")

        def clip_copy():
            clipboard.copy(self.current_room)
            copied = tk.Label(frame, text="Copied!", font=("rockwell", 12), fg="green")
            copied.place(relx=0.71, rely=0.05, anchor="w")
            self.after(2500, copied.destroy)

        tk.Button(
            frame,
            image=self.copy_icon,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=clip_copy,
        ).place(relx=0.68, rely=0.047, anchor="center")

        tk.Label(frame, text=f"Host: {hostname}", font=("rockwell", 13)).place(
            relx=0.5, rely=0.1, anchor="center"
        )

        self.room_members[game] = tk.Frame(frame)
        self.room_members[game].place(
            relx=0.5, rely=0.15, anchor="n", relwidth=0.95, relheight=0.35
        )
        self.room_settings[game] = tk.Frame(frame)
        self.room_settings[game].place(
            relx=0.5, rely=0.525, anchor="n", relwidth=0.95, relheight=0.45
        )

        self.update_room(room, game)

    def update_room(self, room, game=None):
        if room["id"] in self.rooms:
            game = "CHESS" if room["id"] in self.rooms["CHESS"] else "MNPLY"
        for child in self.room_members[game].winfo_children():
            child.destroy()
        tk.Label(
            self.room_members[game],
            text=f"Members",
            font=("impact", 15, "underline"),
        ).place(relx=0.5, rely=0, anchor="n")
        k = 1.1
        d = sorted(room["members"].values(), key=lambda x: x["name"])
        for i in d:
            i.update({"pfp": Arcade.get_pfp(i["name"], (32, 32))})
        for i in d:
            tk.Label(
                self.room_members[game],
                image=i["pfp"],
                text="  " + i["name"],
                font=("rockwell", 13),
                compound="left",
            ).place(relx=0.4, rely=(k / 5), anchor="w")
            k += 1

        settings_dict = self.rooms[game][room["id"]]["settings"]
        display_dict = {
            "STATUS": "Room Type:",
            "TIME": "Minutes per side:",
            "MAX_PLAYERS": "Players Allowed:",
            "HOST_SIDE": "Your Side:",
            "ADD_TIME": "Increment per turn:",
        }
        for child in self.room_settings[game].winfo_children():
            child.destroy()
        frame = self.room_settings[game]
        tk.Label(frame, text="Settings", font=("impact", 15, "underline")).place(
            relx=0.5, rely=0, anchor="n"
        )
        k = 1
        for i in settings_dict:
            if (game == "CHESS" and i == "MAX_PLAYERS") or (
                room["host"] != self.me and i == "HOST_SIDE"
            ):
                continue
            tk.Label(frame, text=display_dict[i], font=("rockwell", 13)).place(
                relx=0.05, rely=0.15 + k / 10, anchor="w"
            )
            k += 1.75

        k = 1
        new_settings = copy.deepcopy(settings_dict)
        if room["host"] == self.me:
            self.apply_button = ttk.Button(
                frame,
                text="APPLY",
                style="12.TButton",
                command=lambda: self.send((room["id"], "SETTINGS", new_settings)),
                state="disabled",
            )
            self.apply_button.place(relx=0.85, rely=1, anchor="s")
            self.room_start_button = ttk.Button(
                frame,
                text="START",
                style="13.TButton",
                command=lambda: self.start_room(game, self.current_room),
                state="disabled",
            )
            self.room_start_button.place(relx=0.5, rely=1, anchor="s")
            try:
                if len(d) > 1:
                    self.room_start_button.configure(state="normal")
                else:
                    self.room_start_button.configure(state="disabled")
            except:
                pass
        else:
            tk.Label(
                frame,
                text="Waiting for Host to start the game",
                font=("rockwell", 13),
            ).place(relx=0.5, rely=1, anchor="s")
        for i, j in settings_dict.items():
            if room["host"] == self.me:

                def check(e, l):
                    try:
                        a = int(e)
                    except:
                        a = 0
                    if (e.isdigit() and a in l) or not e:
                        return True
                    else:
                        return False

                if game == "CHESS" and i == "MAX_PLAYERS":
                    continue

                if i == "STATUS":
                    status_var = tk.StringVar(value=j)

                    def status_change():
                        new_settings["STATUS"] = status_var.get()
                        if new_settings == settings_dict:
                            self.apply_button.configure(state="disabled")
                        else:
                            self.apply_button.configure(state="normal")

                    ttk.Radiobutton(
                        frame,
                        text="Public",
                        variable=status_var,
                        value="PUBLIC",
                        command=status_change,
                    ).place(relx=0.6, rely=0.15 + k / 10, anchor="w")
                    ttk.Radiobutton(
                        frame,
                        text="Private",
                        variable=status_var,
                        value="PRIVATE",
                        command=status_change,
                    ).place(relx=0.8, rely=0.15 + k / 10, anchor="w")

                elif i == "TIME":

                    def tot_time():
                        if not self.time_spin.get():
                            return
                        new_settings["TIME"] = int(self.time_spin.get()) * 60
                        if new_settings == settings_dict:
                            self.apply_button.configure(state="disabled")
                        else:
                            self.apply_button.configure(state="normal")

                    self.time_spin = ttk.Spinbox(
                        frame,
                        validate="key",
                        validatecommand=(
                            self.register(lambda e: check(e, list(range(1, 31)))),
                            "%P",
                        ),
                        from_=1,
                        to=30,
                        increment=1,
                        command=tot_time,
                        wrap=True,
                    )
                    self.time_spin.delete(0, "end")
                    self.time_spin.insert(0, str(j // 60))
                    self.time_spin.place(relx=0.6, rely=0.15 + k / 10, anchor="w")
                    self.time_spin.bind("<KeyRelease>", lambda e: tot_time())
                elif i == "ADD_TIME":

                    def add_time():
                        if not self.add_spin.get():
                            return
                        new_settings["ADD_TIME"] = int(self.add_spin.get())
                        if new_settings == settings_dict:
                            self.apply_button.configure(state="disabled")
                        else:
                            self.apply_button.configure(state="normal")

                    self.add_spin = ttk.Spinbox(
                        frame,
                        validate="key",
                        validatecommand=(
                            self.register(lambda e: check(e, list(range(11)))),
                            "%P",
                        ),
                        from_=0,
                        to=10,
                        increment=1,
                        command=add_time,
                        wrap=True,
                    )
                    self.add_spin.insert(0, str(j))
                    self.add_spin.place(relx=0.6, rely=0.15 + k / 10, anchor="w")
                    self.add_spin.bind("<KeyRelease>", lambda e: add_time())

                elif i == "HOST_SIDE":
                    side_var = tk.StringVar()
                    rand = tk.BooleanVar()
                    if self.updated_host_side == "RANDOM":
                        rand = tk.BooleanVar(value=True)
                    elif self.updated_host_side in ["BLACK", "WHITE"]:
                        side_var.set(self.updated_host_side)
                    else:
                        rand.set(True)

                    def side_change(ch=False):
                        if ch:
                            self.updated_host_side = side_var.get()
                            rand.set(False)
                        else:
                            self.updated_host_side = "RANDOM"
                            side_var.set("")
                        if rand.get():
                            new_settings["HOST_SIDE"] = random.choice(
                                ("BLACK", "WHITE")
                            )
                        else:
                            if not side_var.get():
                                side_var.set("WHITE")
                            new_settings["HOST_SIDE"] = side_var.get()

                        if self.updated_host_side in [
                            new_settings["HOST_SIDE"],
                            "RANDOM",
                        ]:
                            self.apply_button.configure(state="normal")
                        else:
                            self.apply_button.configure(state="normal")

                    ttk.Radiobutton(
                        frame,
                        text="Black",
                        variable=side_var,
                        value="BLACK",
                        command=lambda: side_change(True),
                    ).place(relx=0.4, rely=0.15 + k / 10, anchor="w")
                    ttk.Radiobutton(
                        frame,
                        text="White",
                        variable=side_var,
                        value="WHITE",
                        command=lambda: side_change(True),
                    ).place(relx=0.6, rely=0.15 + k / 10, anchor="w")
                    ttk.Checkbutton(
                        frame,
                        text="Random",
                        variable=rand,
                        offvalue=False,
                        onvalue=True,
                        command=side_change,
                    ).place(relx=0.8, rely=0.15 + k / 10, anchor="w")
                elif i == "MAX_PLAYERS":

                    def max_play():
                        if not self.max_spin.get():
                            return
                        new_settings["MAX_PLAYERS"] = int(self.max_spin.get())
                        if new_settings == settings_dict:
                            self.apply_button.configure(state="disabled")
                        else:
                            self.apply_button.configure(state="normal")

                    self.max_spin = ttk.Spinbox(
                        frame,
                        validate="key",
                        validatecommand=(
                            self.register(lambda e: check(e, list(range(2, 5)))),
                            "%P",
                        ),
                        from_=2,
                        to=4,
                        increment=1,
                        command=max_play,
                        wrap=True,
                    )
                    self.max_spin.insert(0, str(j))
                    self.max_spin.place(relx=0.6, rely=0.15 + k / 10, anchor="w")
                    self.max_spin.bind("<KeyRelease>", lambda e: max_play())
            else:
                if (game == "CHESS" and i == "MAX_PLAYERS") or i == "HOST_SIDE":
                    continue
                txt = j
                if i == "STATUS":
                    txt = j.title()
                elif i == "TIME":
                    txt = str(j // 60)
                elif i == "ADD_TIME":
                    txt = str(j) + " sec"
                tk.Label(frame, text=txt, font=("rockwell", 13)).place(
                    relx=0.6, rely=0.15 + k / 10, anchor="w"
                )
            k += 1.75

    def leave_room(self, room, game=None, delete=False, confirm=True):
        if room in self.rooms:
            game = "CHESS" if room in self.rooms["CHESS"] else "MNPLY"
        if confirm:
            if not self.show_message(
                "Leaving room!",
                f"Do you want to leave the room? {'The Room will be deleted if you leave'if delete else ''}",
                "yesno",
            ):
                return
        self.current_room = None
        self.room_frames[game].destroy()
        self.room_frames[game] = None
        self.send((room, "LEAVE", "Quit"))
        if not delete:
            self.join_lobby(game)

    def start_room(self, game, room):
        self.updated_host_side = None
        self.send((room, "START"))

    # endregion

    # region # Leaderboard & stats

    def leaderboard(self, game):
        parent = self.chess_frame if game == "chess" else self.monopoly_frame

        self.leaderboard_details[game] = sorted(
            HTTP.leaderboard(game).items(), key=lambda i: i[1], reverse=True
        )
        for i, j in self.leaderboard_details[game]:
            self.pfps[game][i] = Arcade.get_pfp(i, (18, 18))

        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.place(relx=0, rely=0.525, anchor="w", relwidth=0.3, relheight=0.9)
        scroll = ttk.Scrollbar(frame, orient="vertical")
        scroll.place(relx=0.9975, rely=0.5, anchor="e", relheight=0.9)

        tk.Label(frame, text="LEADERBOARD", font=("Impact", 15)).place(
            relx=0.5, rely=0.025, anchor="center"
        )

        def refresh():
            self.leaderboard_details[game] = sorted(
                HTTP.leaderboard(game).items(), key=lambda i: i[1], reverse=True
            )
            for i, j in self.leaderboard_details[game]:
                self.pfps[game][i] = Arcade.get_pfp(i, (18, 18), True)
            for i in tree.get_children():
                tree.delete(i)
            for i, j in self.leaderboard_details[game]:
                if j:
                    tree.insert(
                        parent="",
                        index="end",
                        iid=i,
                        text="",
                        image=self.pfps[game][i],
                        values=(
                            self.leaderboard_details[game].index((i, j)) + 1,
                            i,
                            int(j) if float(j).is_integer() else j,
                        ),
                        tag=i,
                    )
            tree.tag_configure(self.name, background="#15a8cd")
            self.config(cursor="")

        def load():
            self.config(cursor="watch")
            self.after(500, refresh)

        tk.Button(
            frame,
            image=self.refresh,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=load,
        ).place(relx=0.98, rely=0.025, anchor="e")

        tree = ttk.Treeview(
            frame,
            columns=("Rank", "Players", "Score"),
            yscrollcommand=scroll.set,
            style="12.Treeview",
        )
        tree.place(relx=0.49, rely=0.5, anchor="center", relheight=0.9, relwidth=0.96)

        scroll.configure(command=tree.yview)
        tree.column(
            "#0",
            width=self.screen_width // 50,
            anchor="center",
            minwidth=self.screen_width // 50,
        )
        tree.column(
            "Rank",
            width=self.screen_width // 50,
            anchor="center",
            minwidth=self.screen_width // 50,
        )
        tree.column(
            "Players",
            width=self.screen_width // 10,
            anchor="center",
            minwidth=self.screen_width // 10,
        )
        tree.column(
            "Score",
            width=self.screen_width // 10,
            anchor="center",
            minwidth=self.screen_width // 10,
        )

        tree.heading("#0", text="")
        tree.heading("Rank", text="Rank", anchor="center")
        tree.heading("Players", text="Players", anchor="center")
        tree.heading(
            "Score",
            text="Points" if game == "chess" else "Highest NetWorth",
            anchor="center",
        )

        for i, j in self.leaderboard_details[game]:
            if j:
                tree.insert(
                    parent="",
                    index="end",
                    iid=i,
                    text="",
                    image=self.pfps[game][i],
                    values=(
                        self.leaderboard_details[game].index((i, j)) + 1,
                        i,
                        int(j) if float(j).is_integer() else j,
                    ),
                    tag=i,
                )
        tree.tag_configure(self.name, background="#15a8cd")

    def stats(self, game):
        parent = self.chess_frame if game == "chess" else self.monopoly_frame
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.place(relx=1, rely=0.525, anchor="e", relwidth=0.3, relheight=0.9)

        def refresh():
            stats = HTTP.stats(game, self.name)
            for i in frame.winfo_children():
                if i != refresh_but:
                    i.destroy()
            if stats == "Bad Request":
                tk.Label(
                    frame, text="No Stats Available!", font=("rockwell", 14)
                ).place(relx=0.5, rely=0.5, anchor="center")
                return
            if game == "chess":
                self.stats_details[game]["Total Games Played"] = len(stats)
                self.stats_details[game]["Number of Games Won"] = len(
                    [i for i in stats if i[-1] == self.name]
                )
                self.stats_details[game]["Number of Games Drawn"] = len(
                    [i for i in stats if i[-1] == "none"]
                )
                self.stats_details[game]["Total Points"] = (
                    len([i for i in stats if i[-1] == self.name])
                    + len([i for i in stats if i[-1] == "none"]) * 0.5
                )
                if self.stats_details[game]["Total Points"].is_integer():
                    self.stats_details[game]["Total Points"] = int(
                        self.stats_details[game]["Total Points"]
                    )
                # ? Add Board Representations display, replay games with PGN, etc.
            else:
                self.stats_details[game]["Total Games Played"] = len(stats)
                self.stats_details[game]["Individual Victories"] = len(
                    [i for i in stats if self.name in i[-1] and len(i[-1]) == 1]
                )
                self.stats_details[game]["Group Victories"] = len(
                    [i for i in stats if self.name in i[-1] and len(i[-1]) != 1]
                )
                self.stats_details[game]["Highest NetWorth"] = max(
                    i[1][self.name]["NETWORTH"] for i in stats
                )
                properties = []
                places = {}
                for i in stats:
                    properties.extend(i[1][self.name]["PROPERTIES"])
                    for j, k in i[1][self.name]["PLACES"].items():
                        places[j] = places.setdefault(j, 0) + k
                try:
                    self.stats_details[game]["Favourite Property"] = max(
                        properties, key=properties.count
                    )
                except ValueError:
                    pass

                self.stats_details[game]["Favourite Spot"] = max(
                    places, key=lambda i: places[i]
                )
            tk.Label(frame, text="YOUR STATS", font=("Impact", 20)).place(
                relx=0.5, rely=0.1, anchor="center"
            )
            k = 0
            for i, j in self.stats_details[game].items():
                tk.Label(
                    frame,
                    text=f"{i} : {j}",
                    font=("rockwell", 14),
                    fg="royalblue" if k % 2 else "aqua",
                ).place(relx=0.5, rely=0.2 + k / 10, anchor="center")
                k += 1

        refresh_but = tk.Button(
            frame,
            image=self.refresh,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=refresh,
        )
        refresh_but.place(relx=0.975, rely=0.025, anchor="e")

        refresh()

    # endregion

    def end_game(self):
        self.deiconify()
        self.current_room = None

    def exit(self):
        if self.current_room:
            if self.show_message(
                "In a Room!",
                "Do you want to leave the room and exit arcade?",
                "yesno",
            ):
                pass
            else:
                return
        try:
            HTTP.logout()
        except:
            pass
        root.quit()
        for file in os.scandir(os.path.join(HOME_ASSETS, "cached_pfp")):
            os.remove(file.path)


class Login(tk.Frame):
    def __init__(self, master, complete, remember_login=False):
        super().__init__(master)
        self.notif = None
        self.notifc = 0
        self.complete = complete

        if remember_login:
            log_win = tk.Toplevel(self)
            log_win.geometry(
                f"{300}x{40}+{self.winfo_screenwidth()//2-150}+{self.winfo_screenheight()//2-20}"
            )
            master.withdraw()
            lbl = tk.Label(
                log_win, text="Logging in...", font=("rockwell", 13), fg="green"
            )
            lbl.pack()
            with open(REMEMBER_ME_FILE, "rb") as f:
                try:
                    uname, pwd = pickle.load(f)
                except:
                    uname = pwd = ""
            self.check_login = HTTP.login(uname, pwd, remember_login=True)
            if self.check_login == 1:
                lbl.configure(text="Loading...")
                self.complete(uname, HTTP.TOKEN)
            elif self.check_login == -1:
                lbl.configure(text="Already Logged in on another device!", fg="red")
            elif self.check_login == 0:
                lbl.configure(text="Invalid Credentials! File Corrupted!", fg="red")
                try:
                    os.remove(REMEMBER_ME_FILE)
                except FileNotFoundError:
                    pass
            else:
                lbl.configure(text="Server Login Error!", fg="red")

            def thing():
                log_win.destroy()
                master.deiconify()

            self.after(1500, thing)

        tk.Label(
            self, text="Welcome to the Arcade!\nPlease Enter your Credentials to Login:"
        ).place(relx=0.5, rely=0.1, anchor="center")
        self.uname = tk.StringVar()
        self.pwd = tk.StringVar()

        tk.Label(self, text="Username: ").place(relx=0.44, rely=0.3, anchor="e")

        def no_special(e):
            if not any(i in ["'", '"', ";", " ", "\\"] for i in e) and len(e) <= 32:
                return True
            else:
                return False

        self.uentry = ttk.Entry(
            self,
            textvariable=self.uname,
            validate="key",
            validatecommand=(
                self.register(no_special),
                "%P",
            ),
        )
        self.uentry.place(relx=0.45, rely=0.3, relwidth=0.2, anchor="w")
        self.uentry.focus_set()
        tk.Label(self, text="Password: ").place(relx=0.44, rely=0.4, anchor="e")
        self.pwdentry = ttk.Entry(self, textvariable=self.pwd, show="*")
        self.pass_hidden = True
        self.pwdentry.place(relx=0.45, rely=0.4, relwidth=0.2, anchor="w")
        self.uentry.bind("<Return>", lambda a: self.pwdentry.focus_set())

        self.login_button = ttk.Button(
            self,
            text="LOGIN",
            style="15.TButton",
            command=self.login,
        )
        self.login_button.place(relx=0.5, rely=0.8, anchor="center")

        def forget_reg():
            self.reg.destroy()

        def register():
            self.reg = Register(self, forget_reg)
            self.reg.place(relx=0.5, rely=0.5, relheight=1, relwidth=1, anchor="center")

        def toggle_hide_password():
            if self.pass_hidden:
                self.pwdentry.config(show="")
                self.show_hide_pass.config(image=self.hide_password)
            else:
                self.pwdentry.config(show="*")
                self.show_hide_pass.config(image=self.show_password)

            self.pass_hidden = not self.pass_hidden

        tk.Button(
            self,
            text="New User? Click Here To Sign Up",
            fg="#15a8cd",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=register,
        ).place(relx=0.5, rely=0.6, anchor="center")

        self.show_password = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "show_password.png")).resize(
                (20, 15), Image.Resampling.LANCZOS
            )
        )

        self.hide_password = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "hide_password.png")).resize(
                (20, 15), Image.Resampling.LANCZOS
            )
        )

        self.show_hide_pass = tk.Button(
            self,
            image=self.show_password,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=toggle_hide_password,
        )
        self.show_hide_pass.place(relx=0.66, rely=0.4, anchor="w")
        self.remember_me = tk.BooleanVar()
        remember_me_button = ttk.Checkbutton(
            self,
            text="Remember Me",
            variable=self.remember_me,
            offvalue=False,
            onvalue=True,
        )
        remember_me_button.place(relx=0.445, rely=0.5, anchor="w")

        self.pwdentry.bind("<Return>", lambda a: self.login())

    def login(self):
        uname = self.uentry.get().strip()
        pwd = self.pwd.get().strip()
        self.pwdentry.delete(0, tk.END)
        msg = ""
        if uname and not pwd:
            msg = "Enter Password"
            self.prompt(msg)
        elif not uname:
            msg = "Enter your Credentials"
            pwd = ""
            self.prompt(msg)
        else:
            try:
                self.check_login = HTTP.login(
                    uname.strip(), pwd.strip(), remember_me=self.remember_me.get()
                )
            except Exception as e:
                logging.exception(e)
                self.destroy()
                msgb.showerror(
                    "Connection Error",
                    "Unable to connect to the Server at the moment, please try again later!\nThings you can do:\n1. Check your network connection\n2. Restart your system\n3. If this issue persists, wait for sometime. The server might be down, We are working on it!",
                    master=root,
                )
                quit()
            if self.check_login:
                if self.check_login != -1:
                    msg = "Logging in..."
                    self.pwdentry.config(state="disabled")
                    self.uentry.config(state="disabled")
                    self.login_button.config(state="disabled")
                    self.pwdentry.unbind("<Return>")
                    self.uentry.unbind("<Return>")
                    self.prompt(msg)
                    if isinstance(self.check_login, str):
                        self.store_password(uname.strip(), self.check_login)
                    self.after(1500, lambda: self.complete(uname, HTTP.TOKEN))
                else:
                    msg = "User logged in on another device!"
                    self.prompt(msg)
            else:
                msg = "Incorrect Username or Password"
                self.prompt(msg)

    def store_password(self, uname, pwd):
        with open(
            REMEMBER_ME_FILE,
            "wb",
        ) as f:
            pickle.dump((uname, pwd), f)

    def prompt(self, msg):
        try:
            self.destroyprompt()
            self.notifc += 1
            color = "red"
            if msg == "Logging in...":
                color = "green"
            self.notif = (
                tk.Label(self, text=msg, fg=color),
                self.notifc,
            )
            self.notif[0].place(relx=0.5, rely=0.67, anchor="center")
            self.after(3000, self.destroyprompt)
        except:
            pass

    def destroyprompt(self):
        if self.notif and self.notif[1] == self.notifc:
            self.notif[0].destroy()
            self.notif = None


class Register(tk.Frame):
    def __init__(self, master, complete):
        super().__init__(master)
        tk.Label(
            self,
            text="Welcome to the Arcade!\nPlease Enter your Details to Create an Account:",
        ).place(relx=0.5, rely=0.1, anchor="center")
        self.uname = tk.StringVar()
        self.pwd = tk.StringVar()
        self.confpwd = tk.StringVar()
        tk.Button(
            self,
            text="← Sign In",
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=self.destroy,
        ).place(relx=0.01, rely=0.01, anchor="nw")
        self.bind("<Escape>", lambda a: self.destroy())
        tk.Label(self, text="Create Username: ").place(relx=0.24, rely=0.3, anchor="e")

        def no_special(e):
            if not any(i in ["'", '"', ";", " ", "\\"] for i in e) and len(e) <= 32:
                return True
            else:
                return False

        self.uentry = ttk.Entry(
            self,
            textvariable=self.uname,
            validate="key",
            validatecommand=(
                self.register(no_special),
                "%P",
            ),
        )
        self.uentry.place(relx=0.25, rely=0.3, relwidth=0.2, anchor="w")
        self.uentry.focus_set()
        tk.Label(self, text="Create Password: ").place(relx=0.24, rely=0.4, anchor="e")
        self.pwdentry = ttk.Entry(self, textvariable=self.pwd, show="*")
        self.pass_hidden = True
        self.pwdentry.place(relx=0.25, rely=0.4, relwidth=0.2, anchor="w")
        tk.Label(self, text="Confirm Password: ").place(relx=0.24, rely=0.5, anchor="e")
        self.confpwdentry = ttk.Entry(self, textvariable=self.confpwd, show="*")
        self.conf_pass_hidden = True
        self.confpwdentry.place(relx=0.25, rely=0.5, relwidth=0.2, anchor="w")

        self.uentry.bind("<Return>", lambda a: self.pwdentry.focus_set())
        self.pwdentry.bind("<Return>", lambda a: self.confpwdentry.focus_set())

        self.reg_button = ttk.Button(
            self,
            text="REGISTER",
            style="15.TButton",
            command=self.reg_user,
        )
        self.reg_button.place(relx=0.5, rely=0.8, anchor="center")

        self.show_password = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "show_password.png")).resize(
                (20, 15), Image.Resampling.LANCZOS
            )
        )

        self.hide_password = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "hide_password.png")).resize(
                (20, 15), Image.Resampling.LANCZOS
            )
        )

        self.show_hide_pass = tk.Button(
            self,
            image=self.show_password,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: toggle_hide_password(False),
        )
        self.show_hide_conf_pass = tk.Button(
            self,
            image=self.show_password,
            highlightthickness=0,
            cursor="hand2",
            border=0,
            command=lambda: toggle_hide_password(True),
        )
        self.show_hide_pass.place(relx=0.46, rely=0.4, anchor="w")
        self.show_hide_conf_pass.place(relx=0.46, rely=0.5, anchor="w")

        for i in self.winfo_children():
            i.bind("<Escape>", lambda a: self.destroy())

        def toggle_hide_password(conf):
            if conf:
                if self.conf_pass_hidden:
                    self.confpwdentry.config(show="")
                    self.show_hide_conf_pass.config(image=self.hide_password)
                else:
                    self.confpwdentry.config(show="*")
                    self.show_hide_conf_pass.config(image=self.show_password)
                self.conf_pass_hidden = not self.conf_pass_hidden
            else:
                if self.pass_hidden:
                    self.pwdentry.config(show="")
                    self.show_hide_pass.config(image=self.hide_password)
                else:
                    self.pwdentry.config(show="*")
                    self.show_hide_pass.config(image=self.show_password)
                self.pass_hidden = not self.pass_hidden

        self.confpwdentry.bind("<Return>", lambda a: self.reg_user())

        self.notif = None
        self.notifc = 0
        self.complete = complete
        self.pfp_path = os.path.join(HOME_ASSETS, "default_pfp.png")
        self.pfp_select()

    def pfp_select(self):
        self.pfp_image = ImageTk.PhotoImage(
            Arcade.circle_PIL_Image(Image.open(self.pfp_path), (100, 100))
        )
        tk.Label(self, image=self.pfp_image).place(relx=0.8, rely=0.26, anchor="center")
        self.remove_image = ImageTk.PhotoImage(
            Image.open(os.path.join(HOME_ASSETS, "remove.png")).resize(
                (32, 32),
                Image.Resampling.LANCZOS,
            )
        )

        def choose():
            n = fd.askopenfilename(
                title="Choose a Profile Picture",
                initialdir=r"%userprofile%",
                filetypes=(("Image Files", "*.jpg *.png *.webp *.gif *.jpeg"),),
            )
            self.pfp_path = n if n else self.pfp_path
            self.pfp_select()

        def set_default():
            self.pfp_path = os.path.join(HOME_ASSETS, "default_pfp.png")
            self.pfp_select()

        self.remove_button = tk.Button(
            self,
            image=self.remove_image,
            cursor="hand2",
            border=0,
            highlightthickness=0,
            command=set_default,
        )
        if self.pfp_path == os.path.join(HOME_ASSETS, "default_pfp.png"):
            self.remove_button.destroy()
        else:
            self.remove_button.place(relx=0.9, rely=0.35, anchor="center")

        self.choose_button = ttk.Button(
            self,
            text="Upload Picture",
            style="15.TButton",
            command=choose,
        )
        self.choose_button.place(relx=0.8, rely=0.51, anchor="center")

    @staticmethod
    def check_pass(pwd):
        check = {
            "length": False,
            "space": True,
        }
        if len(pwd) >= 4:
            check["length"] = True
        if any(i.isspace() for i in pwd):
            check["space"] = False

        return [i for i, j in check.items() if not j]

    def reg_user(self):
        uname = self.uentry.get().strip()
        pwd = self.pwd.get().strip()
        confpwd = self.confpwd.get().strip()

        self.confpwdentry.delete(0, tk.END)
        prompts = {
            "length": "Atleast 4 Characters",
            "space": "No Spaces",
        }
        missing = Register.check_pass(pwd)

        msg = ""
        if uname in ["none", "Unknown"]:
            self.uentry.delete(0, tk.END)
            msg = "Illegal Username!"
            self.prompt(msg)
        elif uname and not pwd:
            self.pwdentry.delete(0, tk.END)
            msg = "Enter Password"
            self.prompt(msg)
        elif uname and pwd and not confpwd:
            msg = "Confirm Password"
            self.prompt(msg)
        elif not uname:
            msg = "Enter your Credentials"
            pwd = ""
            confpwd = ""
            self.pwdentry.delete(0, tk.END)
            self.prompt(msg)
        elif missing:
            self.pwdentry.delete(0, tk.END)
            msg = "Password should have:"
            for i in missing:
                msg += "\n" + prompts[i]
            self.prompt(msg)
        elif confpwd != pwd:
            msg = "Password does not match"
            self.prompt(msg)
        else:
            try:
                if HTTP.register(
                    uname.strip(),
                    pwd.strip(),
                    Arcade.pfp_send(self.pfp_path),
                ):
                    msg = "Registering..."
                    self.prompt(msg)
                    self.after(1000, self.complete)
                else:
                    self.uentry.delete(0, tk.END)
                    self.pwdentry.delete(0, tk.END)
                    msg = "User Already Registered"
                    self.prompt(msg)
            except Exception as e:
                logging.exception(e)
                self.destroy()
                msgb.showerror(
                    "Try Again Later",
                    "Unable to connect to the Server at the moment, please try again later!\nThings you can do:\n1. Check your network connection\n2. Restart your system\n3. If this issue persists, wait for sometime. The server might be down, We are working on it!",
                    master=root,
                )
                quit()

    def prompt(self, msg):
        try:
            self.destroyprompt()
            self.notifc += 1
            color = "red"
            if msg == "Registering...":
                color = "green"
            self.notif = (
                tk.Label(self, text=msg, fg=color),
                self.notifc,
            )
            self.notif[0].place(relx=0.25, rely=0.7, anchor="center")
            self.after(5000, self.destroyprompt)
        except:
            pass

    def destroyprompt(self):
        if self.notif and self.notif[1] == self.notifc:
            self.notif[0].destroy()
            self.notif = None


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Arcade")
    try:
        os.mkdir(os.path.join(HOME_ASSETS, "cached_pfp"))
    except:
        pass
    try:
        os.mkdir(
            os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "Arcade",
            )
            if isWin
            else os.path.join(
                os.environ["HOME"],
                "Applications",
                "Arcade",
            )
        )
    except:
        pass
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "wb") as f:
            pickle.dump({"THEME": "dark", "DEFAULT_GAME": 0}, f)
            CURR_THEME = "dark"
    else:
        with open(SETTINGS_FILE, "rb") as f:
            d = pickle.load(f)
            if d["THEME"] in ["dark", "light"]:
                CURR_THEME = d["THEME"]
            else:
                CURR_THEME = "dark"
                with open(SETTINGS_FILE, "rb+") as f:
                    d = pickle.load(f)
                    d.update({"THEME": "dark"})
                    f.seek(0)
                    pickle.dump(d, f)

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "a") as f:
            f.write("\n\n\n")

    theme = Theme(root, CURR_THEME)
    arc = Arcade()
    try:
        arc.start_arcade()
        root.mainloop()
    except Exception as e:
        logging.exception(e)
        msgb.showerror(
            "Try Again Later",
            "Unable to connect to the Server at the moment, please try again later!\nThings you can do:\n1. Check your network connection\n2. Restart your system\n3. If this issue persists, wait for sometime. The server might be down, We are working on it!",
            master=root,
        )
