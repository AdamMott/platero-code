#!/usr/bin/env python

import os
import logging
from configparser import ConfigParser

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as tkdialog
from tkinter import messagebox as tkmessagebox

from platero.utils import setup_logging, resource_path, bundled_app
from process_plates import process_plates, RESULTS_FILENAME


def pad_all(widget):
    for child in widget.winfo_children():
        child.grid_configure(padx=5, pady=3)
        pad_all(child)

def os_open(path):
    '''
    (Hopefully) Platform independent way to open a file/folder
    '''
    import os, sys, subprocess

    if sys.platform == "win32":
        os.startfile(path)
    else:
        opener ="open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, path])


class SelectPath(ttk.Frame):

    def __init__(self, master=None, label="Path", folder=False):
        ttk.Frame.__init__(self, master)
        self.folder = folder
        self.selectedPath = tk.StringVar()

        ttk.Label(self, text=label, width=10).grid(row=0, column=0, sticky="W")
        ttk.Entry(self, textvariable=self.selectedPath, state="readonly", width=50).grid(row=0, column=1, sticky="EW")
        self.columnconfigure(1, weight=1)
        self.btn_select = ttk.Button(self, text="Select", command=self.select_path)
        self.btn_select.grid(row=0, column=2)

        self.btn_open = ttk.Button(self, text="Open", command=self.open_path, state="disabled")
        self.btn_open.grid(row=0, column=3)
        self.selectedPath.trace("w", self.enable_actions)

    @property
    def path(self):
        return self.selectedPath.get()

    @path.setter
    def path(self, value):
        self.selectedPath.set(value)

    def select_path(self):
        if self.folder:
            path = tkdialog.askdirectory(initialdir=self.path, title="Please select a folder")
        else:
            path = tkdialog.askopenfilename(initialfile=self.path, title="Please select a file")

        if path:
            self.path = path

    def enable_actions(self, *args):
        if self.selectedPath.get():
            self.btn_open.config(state="normal")

    def open_path(self):
        os_open(self.path)


class LogConsole(tk.Text):
    # TODO: make this with tkinter and include inside ttk.LabelFrame
    def __init__(self, root, **options):
        tk.Text.__init__(self, root, **options)
        # TODO: maybe add a scrollbar
        # self.scrollbar = tk.Scrollbar(self.master)
        # self.config(yscrollcommand=self.scrollbar.set)
        # self.scrollbar.config(command=self.yview)
        self.config(state='disabled')
        self.config(background='black')
        self.tag_config(logging.ERROR, foreground="red")
        self.tag_config(logging.WARNING, foreground="yellow")
        self.tag_config(logging.INFO, foreground="white")
        self.tag_config(logging.DEBUG, foreground="green")

    def log(self, record, level=logging.INFO):
        self.config(state='normal')
        self.insert(tk.END, record, level)
        self.config(state='disabled')
        self.see(tk.END)

    def reset(self):
        self.config(state='normal')
        self.delete('1.0', tk.END)
        self.config(state='disabled')

class NoExceptionFormatter(logging.Formatter):
    def format(self, record):
        record.exc_text = ''
        return super(NoExceptionFormatter, self).format(record)

    def formatException(self, record):
        return ''

class LogToGUI(logging.Handler):
    def __init__(self, console):
        logging.Handler.__init__(self)
        self.console = console
        self.setLevel(logging.INFO)
        self.setFormatter(NoExceptionFormatter('%(message)s\n'))

    def emit(self, record):
        self.console.log(self.format(record), record.levelno)

class PlateroGUI(ttk.Frame):

    def __init__(self, master=None):
        ttk.Frame.__init__(self, master)
        self.pack(fill=tk.BOTH, expand=tk.YES)
        self.create_widgets()
        self.enable_actions()
        self.file_log = None

    def create_widgets(self):
        self.wdg_platesFolder = SelectPath(self, "Plates folder", True)
        self.wdg_platesFolder.selectedPath.trace("w", self.enable_actions)
        self.wdg_proteinsList = SelectPath(self, "Protein list")
        self.wdg_proteinsList.selectedPath.trace("w", self.enable_actions)
        self.wdg_outputFolder = SelectPath(self, "Output folder", True)
        self.wdg_outputFolder.selectedPath.trace("w", self.enable_actions)
        self.txt_console = LogConsole(self, height="30", width="160")

        self.btn_processPlates = ttk.Button(self, text="Process plates", command=self.start_process, state="disabled")

        self.columnconfigure(0, weight=1)
        self.wdg_platesFolder.grid(row=0, column=0, sticky="EW")
        self.wdg_proteinsList.grid(row=1, column=0, sticky="EW")
        self.wdg_outputFolder.grid(row=2, column=0, sticky="EW")
        self.btn_processPlates.grid(row=3, column=0)
        self.txt_console.grid(row=4, column=0, sticky=tk.NSEW)

        pad_all(self)

    def enable_actions(self, *args):
        if self.wdg_platesFolder.selectedPath.get() \
            and self.wdg_proteinsList.selectedPath.get() \
            and self.wdg_outputFolder.selectedPath.get():
            self.btn_processPlates.config(state="normal")

    def start_process(self):
        import threading
        self.thread_process = threading.Thread(target=self.process_plates)
        # Set Daemon to True, so thread is closed on exit
        self.thread_process.setDaemon(True)
        self.thread_process.start()

    def process_plates(self):
        self.btn_processPlates.config(state="disabled")

        # Check if main output file already exists
        proceed = True
        if os.path.isfile( os.path.join(self.wdg_outputFolder.path, RESULTS_FILENAME) ):
            proceed = tkmessagebox.askquestion("Please confirm", "A results file already exists in the "+ \
                                     "destination folder and will be overwritten. Are you sure "+ \
                                     "you want to proceed?", icon='warning') == 'yes'
        if proceed:
            self.change_filelog()
            self.txt_console.reset()
            try:
                process_plates(self.wdg_platesFolder.path, self.wdg_proteinsList.path, self.wdg_outputFolder.path)
            except Exception as exc:
                logging.error("Plates couldn't be processed, see error below")
                logging.exception(exc)
                tkmessagebox.showerror("An error ocurred", exc)
            else:
                logging.info("Plates processed successfully. Results stored under {}".format(self.wdg_outputFolder.path))
                tkmessagebox.showinfo("Success!", "Plates processed successfully and results stored in the selected output folder")

        self.btn_processPlates.config(state="normal")

    def change_filelog(self):
        logger = logging.getLogger()

        if self.file_log:
            logger.removeHandler(self.file_log)

        self.file_log = logging.FileHandler(os.path.join(self.wdg_outputFolder.path, 'platero.log'))
        self.file_log.setLevel(logging.DEBUG)
        self.file_log.setFormatter(logging.Formatter('[%(levelname)s] %(asctime)s : %(message)s'))

        logger.addHandler(self.file_log)


class PlateroApp(tk.Tk):
    APP_NAME = 'Platero GUI'
    APP_VERSION = 'v0.1.4'
    CONFIG_FILE = 'config.ini'

    def __init__(self):
        tk.Tk.__init__(self)
        icon = tk.PhotoImage(file=resource_path('assets/gui/icon.gif'))
        self.tk.call('wm', 'iconphoto', self._w, icon)
        self.title(self.APP_NAME + ' ' + self.APP_VERSION)
        self.resizable(width=True, height=False)
        self.set_config_path()
        self.app = PlateroGUI(master=self)
        self.setup_logging()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.on_open()
        self.app.mainloop()

    def set_config_path(self):
        if bundled_app():
            from os.path import expanduser
            # TODO: make platform independent
            folder = os.path.join(expanduser("~"), "Library", "Platero")
            if not os.path.isdir(folder):
                os.makedirs(folder)

            self.CONFIG_FILE = os.path.join(folder, self.CONFIG_FILE)

    def setup_logging(self):
        logger = logging.getLogger()
        logger.addHandler(LogToGUI(self.app.txt_console))
        logging.info('Platero started successfully')

    def on_open(self):
        self.load_config()

    def on_top(self):
        self.lift()
        self.call('wm', 'attributes', '.', '-topmost', True)
        self.after_idle(self.call, 'wm', 'attributes', '.', '-topmost', False)

    def halt_processing(self):
        # NOTE: this has been solved by setting the thread as a daemon
        # before starting it
        pass

    def on_close(self):
        self.save_config()
        self.halt_processing()
        self.destroy()

    def load_config(self):
        if os.path.isfile(self.CONFIG_FILE):
            config = ConfigParser()
            config.read(self.CONFIG_FILE)
            self.app.wdg_platesFolder.path = get_with_default(config, 'options', 'plates_folder')
            self.app.wdg_proteinsList.path = get_with_default(config, 'options', 'proteins_list')
            self.app.wdg_outputFolder.path = get_with_default(config, 'options', 'output_folder')

    def save_config(self):
        with open(self.CONFIG_FILE, 'w') as file:
            config = ConfigParser()
            config.add_section('options')
            config.set('options', 'plates_folder', self.app.wdg_platesFolder.path)
            config.set('options', 'proteins_list', self.app.wdg_proteinsList.path)
            config.set('options', 'output_folder', self.app.wdg_outputFolder.path)
            config.write(file)

def get_with_default(config, section,name, default=''):
    '''
    Get an option from a config file with a default value
    '''
    if config.has_option(section, name):
        return config.get(section, name)
    else:
        return default


if __name__ == '__main__':
    setup_logging(logging.INFO)
    # TODO:
    # 1. Deal with repeated value
    # 6. Should we remove the not cloned from the batches?
    PlateroApp()
