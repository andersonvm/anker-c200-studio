#!/usr/bin/env python3
"""Anker C200 Studio — GUI Tkinter para o CLI anker-powerconf-c200-linux-tools.
Sem dependências Python externas. Não grava configurações automaticamente.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import cv2
    from PIL import Image, ImageTk
except ImportError:
    cv2 = None
    Image = ImageTk = None

APP = 'Anker C200 Studio'
EXECUTABLE = 'anker-powerconf-c200-linux-tools'
HOME = Path.home()
PROFILE_DIR = HOME / '.config' / 'anker-c200-studio' / 'profiles'
# Limites extraídos da câmera C200 do usuário (v4l2-ctl).
SPECS = {
 'fov': ('Campo de visão', 'choice', {'65': '65° · Próximo', '78': '78° · Médio', '95': '95° · Amplo'}),
 'hdr': ('HDR', 'choice', {'off': 'Desligado', 'on': 'Ligado'}),
 'brightness': ('Brilho', 'slider', (0, 100, 1)),
 'contrast': ('Contraste', 'slider', (0, 100, 1)),
 'saturation': ('Saturação', 'slider', (0, 100, 1)),
 'hue': ('Matiz', 'slider', (0, 3, 1)),
 'gamma': ('Gama', 'slider', (0, 800, 1)),
 'sharpness': ('Nitidez', 'slider', (0, 100, 1)),
 'white_balance_automatic': ('Balanço de branco automático', 'choice', {'off':'Manual', 'on':'Automático'}),
 'white_balance_temperature': ('Temperatura de cor (K)', 'slider', (2300, 6500, 1)),
 'power_line_frequency': ('Frequência da rede', 'choice', {'0':'Desativado', '1':'50 Hz', '2':'60 Hz'}),
 'anti_flicker': ('Anti-flicker (proprietário)', 'number', (0, 255)),
 'auto_exposure': ('Modo de exposição', 'choice', {'0':'0 · Atual/padrão', '1':'1 · Manual', '2':'2 · Outro', '3':'3 · Outro'}),
 'exposure_time_absolute': ('Tempo de exposição', 'slider', (1, 1000, 1)),
 'horizontal_flip': ('Espelhamento horizontal', 'choice', {'off':'Desligado', 'on':'Ligado'}),
 'zoom_absolute': ('Zoom', 'slider', (100, 400, 1)),
 'pan_absolute': ('Panorâmica', 'slider', (-36000, 36000, 3600)),
 'tilt_absolute': ('Inclinação', 'slider', (-36000, 36000, 3600)),
 'focus_automatic_continuous': ('Foco automático', 'choice', {'off':'Manual', 'on':'Automático'}),
 'focus_absolute': ('Foco manual', 'slider', (300, 650, 1)),
 'vertical_screen': ('Orientação vertical', 'number', (0, 255)),
}
TABS = {
 'Imagem': ['fov','hdr','brightness','contrast','saturation','hue','gamma','sharpness'],
 'Iluminação': ['white_balance_automatic','white_balance_temperature','power_line_frequency','anti_flicker','auto_exposure','exposure_time_absolute'],
 'Enquadramento': ['horizontal_flip','zoom_absolute','pan_absolute','tilt_absolute','focus_automatic_continuous','focus_absolute','vertical_screen'],
}
DEPENDENCIES = {
 'white_balance_temperature': ('white_balance_automatic', 'on'),
 'focus_absolute': ('focus_automatic_continuous', 'on'),
}

def default_binary():
    candidates = ['/usr/lib/anker-c200-studio/anker-powerconf-c200-linux-tools', shutil.which('anker-c200'), shutil.which(EXECUTABLE),
        str(HOME/'Downloads'/'anker-powerconf-c200-linux-tools-v0.1.0-linux-amd64'/EXECUTABLE)]
    candidates += [str(p) for p in sorted((HOME/'Downloads').glob('anker-powerconf-c200-linux-tools*/'+EXECUTABLE))]
    return next((p for p in candidates if p and Path(p).is_file() and os.access(p, os.X_OK)), '')

def cli(binary, device, *args):
    proc = subprocess.run([binary,'--device',device,*args], capture_output=True, text=True, timeout=7)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout or 'Erro desconhecido').strip())
    return proc.stdout.strip()

def normalize(key, result):
    result = result.strip()
    if key == 'fov': return result.split(' ',1)[0]
    return result

class Control:
    def __init__(self, app, parent, key, row):
        self.app, self.key = app, key
        title, kind, options = SPECS[key]
        self.kind, self.options = kind, options
        self.available = False
        self.reason = 'Não consultado'
        self.var = tk.StringVar(value='')
        self.status = tk.StringVar(value='—')
        ttk.Label(parent,text=title).grid(row=row,column=0,sticky='w',padx=(10,16),pady=9)
        frame=ttk.Frame(parent)
        frame.grid(row=row,column=1,sticky='ew',padx=(0,8))
        self.label=None
        if kind == 'slider':
            low,high,step=options
            self.slider=ttk.Scale(frame,from_=low,to=high,command=self.drag)
            self.slider.pack(side='left',fill='x',expand=True)
            self.slider.bind('<ButtonRelease-1>',lambda _e:self.on_release())
            self.label=ttk.Label(frame,width=8,text='—',anchor='e')
            self.label.pack(side='right',padx=(8,0))
            self.field=self.slider
        elif kind=='choice':
            self.mapping={v:k for k,v in options.items()}
            self.field=ttk.Combobox(frame,values=list(self.mapping),state='readonly',textvariable=self.var,width=29)
            self.field.pack(side='left',fill='x',expand=True)
        else:
            self.field=ttk.Entry(frame,textvariable=self.var,width=15)
            self.field.pack(side='left',anchor='w')
            ttk.Label(frame,text='Valor inteiro',foreground='#687182').pack(side='left',padx=12)
        self.apply_btn=ttk.Button(parent,text='Aplicar',command=self.apply)
        self.apply_btn.grid(row=row,column=2,padx=8)
        ttk.Label(parent,textvariable=self.status,width=23,anchor='w').grid(row=row,column=3,padx=(8,10),sticky='w')
        self.disable('Não consultado')

    def drag(self,value):
        low,high,step=self.options
        n=max(low,min(high,low+round((float(value)-low)/step)*step))
        self.var.set(str(n))
        self.label.configure(text=str(n))

    def on_release(self):
        if self.app.auto_apply.get() and self.available and not self.app.busy:
            self.apply()

    def set_value(self,value):
        value=normalize(self.key,value)
        if self.kind=='slider':
            try: v=int(value)
            except ValueError: raise ValueError(f'Valor inesperado: {value!r}')
            self.slider.set(v)
            self.drag(str(v))
        elif self.kind=='choice':
            if value not in self.options:
                raise ValueError(f'Valor não mapeado: {value!r}')
            self.var.set(self.options[value])
        else: self.var.set(value)

    def value(self):
        if self.kind=='choice':
            value=self.mapping.get(self.var.get())
            if value is None: raise ValueError('Selecione uma opção')
            return value
        if self.kind=='slider':
            low,high,step=self.options
            v=int(self.var.get())
            return str(max(low,min(high,low+round((v-low)/step)*step)))
        val=int(self.var.get())
        low,high=self.options
        if not low<=val<=high: raise ValueError(f'Informe valor entre {low} e {high}')
        return str(val)

    def disable(self,why):
        self.reason=why
        self.status.set('Indisponível' if why != 'Não consultado' else 'Não consultado')
        self.available=False
        self.field.state(['disabled'])
        self.apply_btn.state(['disabled'])

    def enable(self):
        self.available=True
        self.reason=''
        self.status.set('Disponível')
        if self.kind=='choice': self.field.configure(state='readonly')
        else: self.field.state(['!disabled'])
        self.apply_btn.state(['!disabled'])

    def apply(self):
        if not self.available:return
        try: val=self.value()
        except (ValueError,TypeError) as exc:
            messagebox.showwarning('Valor inválido',str(exc));return
        self.app.apply_one(self.key,val)

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry('1370x840')
        self.minsize(1020,620)
        self.binary=tk.StringVar(value=default_binary())
        self.device=tk.StringVar(value='/dev/video0')
        self.auto_apply=tk.BooleanVar(value=True)
        self.resolution=tk.StringVar(value='1280x720')
        self.fps=tk.StringVar(value='30')
        self.capture_info=('—', '—')
        self.message=tk.StringVar(value='Conecte a webcam e clique em Atualizar.')
        self.controls={}
        self.errors={}
        self.inactive=set()
        self.busy=False
        self.preview_running=False
        self.preview_stop=threading.Event()
        self.latest_frame=None
        self.frame_lock=threading.Lock()
        self.preview_photo=None
        self.preview_error=None
        self.snapshot_frame=None
        self.preview_generation=0
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.build()
        self.after(50,self.show_frame)
        self.after(250,self.refresh)

    def build(self):
        header=ttk.Frame(self,padding=(16,14))
        header.pack(fill='x')
        ttk.Label(header,text=APP,font=('',20,'bold')).grid(row=0,column=0,columnspan=4,sticky='w',pady=(0,10))
        ttk.Label(header,text='Executável:').grid(row=1,column=0,sticky='w')
        ttk.Entry(header,textvariable=self.binary).grid(row=1,column=1,columnspan=2,sticky='ew',padx=8)
        ttk.Button(header,text='Procurar…',command=self.pick).grid(row=1,column=3)
        ttk.Label(header,text='Dispositivo:').grid(row=2,column=0,sticky='w',pady=(10,0))
        ttk.Entry(header,textvariable=self.device,width=17).grid(row=2,column=1,sticky='w',padx=8,pady=(10,0))
        header.columnconfigure(1,weight=1)
        header.columnconfigure(2,weight=1)
        bar=ttk.Frame(self,padding=(16,2,16,12));bar.pack(fill='x')
        self.refresh_btn=ttk.Button(bar,text='Atualizar da câmera',command=self.refresh);self.refresh_btn.pack(side='left')
        ttk.Checkbutton(bar,text='Aplicar slider ao soltar',variable=self.auto_apply).pack(side='left',padx=14)
        ttk.Button(bar,text='Salvar perfil…',command=self.save_profile).pack(side='right',padx=(7,0))
        ttk.Button(bar,text='Carregar perfil…',command=self.load_profile).pack(side='right')
        content=ttk.Panedwindow(self,orient='horizontal')
        content.pack(fill='both',expand=True,padx=12,pady=(0,8))
        controls_panel=ttk.Frame(content)
        video_panel=ttk.Frame(content,padding=(10,6))
        content.add(controls_panel,weight=3)
        content.add(video_panel,weight=2)
        self.notebook=ttk.Notebook(controls_panel)
        self.notebook.pack(fill='both',expand=True)
        ttk.Label(video_panel,text='Pré-visualização em tempo real',font=('',13,'bold')).pack(anchor='w',pady=(4,10))
        self.preview_canvas=tk.Canvas(video_panel,bg='#141820',highlightthickness=0,width=420,height=280)
        self.preview_canvas.pack(fill='both',expand=True)
        self.preview_status=tk.StringVar(value='Pré-visualização desligada')
        ttk.Label(video_panel,textvariable=self.preview_status,wraplength=450).pack(anchor='w',pady=(8,6))
        settings=ttk.Frame(video_panel)
        settings.pack(fill='x',pady=(0,10))
        ttk.Label(settings,text='Resolução').pack(side='left')
        self.res_combo=ttk.Combobox(settings,textvariable=self.resolution,state='readonly',width=11,
                                   values=['640x480','1280x720','1920x1080','2560x1440'])
        self.res_combo.pack(side='left',padx=(7,15))
        ttk.Label(settings,text='FPS').pack(side='left')
        self.fps_combo=ttk.Combobox(settings,textvariable=self.fps,state='readonly',width=6,
                                   values=['15','24','30','60'])
        self.fps_combo.pack(side='left',padx=7)
        ttk.Button(settings,text='Aplicar vídeo',command=self.change_capture).pack(side='left',padx=7)
        video_actions=ttk.Frame(video_panel)
        video_actions.pack(fill='x')
        self.preview_btn=ttk.Button(video_actions,text='Iniciar vídeo',command=self.toggle_preview)
        self.preview_btn.pack(side='left')
        ttk.Button(video_actions,text='Capturar imagem…',command=self.save_snapshot).pack(side='left',padx=8)
        ttk.Label(video_panel,text="A imagem acompanha os ajustes aplicados à câmera. Se Teams, Zoom ou navegador estiverem usando a webcam, a abertura poderá falhar.",foreground="#687182",wraplength=440).pack(anchor="w",pady=(12,0))
        for tab,keys in TABS.items():
            panel=ttk.Frame(self.notebook,padding=12)
            self.notebook.add(panel,text=tab)
            panel.columnconfigure(1,weight=1)
            for row,key in enumerate(keys): self.controls[key]=Control(self,panel,key,row)
        footer=ttk.Frame(self,padding=(16,10));footer.pack(fill='x')
        ttk.Label(footer,textvariable=self.message,wraplength=980).pack(anchor='w')
        ttk.Label(footer,text='Alterações só são enviadas ao clicar Aplicar ou ao soltar o slider com a opção marcada.',
                  foreground='#687182').pack(anchor='w',pady=(6,0))

    def change_capture(self):
        if self.preview_running:
            self.stop_preview()
            # Evento anterior será liberado antes de criar nova captura.
            self.after(250,self.start_preview)
        else:
            self.preview_status.set('Configuração de vídeo selecionada; clique em Iniciar vídeo.')

    def toggle_preview(self):
        if self.preview_running:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self):
        if cv2 is None or Image is None:
            messagebox.showerror('Dependências do vídeo',
                'Instale os pacotes do Ubuntu: sudo apt install python3-opencv python3-pil python3-pil.imagetk')
            return
        device=self.device.get().strip()
        if not re.fullmatch(r'/dev/video\d+',device):
            messagebox.showerror('Dispositivo inválido','Informe /dev/video0 ou outro dispositivo de vídeo.')
            return
        self.preview_generation+=1
        generation=self.preview_generation
        self.preview_stop=threading.Event()
        stop_event=self.preview_stop
        self.preview_running=True
        self.preview_btn.configure(text='Parar vídeo')
        self.preview_status.set('Conectando à câmera…')
        self.preview_error=None
        with self.frame_lock:self.latest_frame=None
        w,h=map(int,self.resolution.get().split('x'))
        fps=int(self.fps.get())
        threading.Thread(target=self.video_worker,args=(device,generation,w,h,fps,stop_event),daemon=True).start()

    def video_worker(self,device,generation,width,height,fps,stop_event):
        cap=None
        try:
            cap=cv2.VideoCapture(device,cv2.CAP_V4L2)
            if not cap.isOpened():
                raise RuntimeError('Não foi possível abrir '+device+'; verifique permissões e outros aplicativos.')
            # MJPEG costuma permitir altas resoluções em câmeras USB UVC.
            cap.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT,height)
            cap.set(cv2.CAP_PROP_FPS,fps)
            actual=(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    round(cap.get(cv2.CAP_PROP_FPS),1))
            self.capture_info=actual
            cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
            failures=0
            while not stop_event.is_set() and generation==self.preview_generation:
                ok,frame=cap.read()
                if not ok:
                    failures+=1
                    if failures>30:raise RuntimeError('Não foi possível capturar quadros da câmera.')
                    time.sleep(.08)
                    continue
                failures=0
                # Apenas o quadro mais novo é mantido para não acumular atraso.
                frame=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                with self.frame_lock:
                    self.latest_frame=frame
                    self.snapshot_frame=frame
        except Exception as exc:
            if generation==self.preview_generation:
                self.preview_error=str(exc)
        finally:
            if cap is not None:cap.release()

    def stop_preview(self):
        self.preview_generation+=1
        self.preview_stop.set()
        self.preview_running=False
        self.preview_btn.configure(text='Iniciar vídeo')
        self.preview_status.set('Pré-visualização desligada')

    def show_frame(self):
        try:
            if self.preview_running and self.preview_error:
                error=self.preview_error
                self.stop_preview()
                self.preview_status.set('Erro: '+error)
            elif self.preview_running:
                with self.frame_lock:
                    frame=self.latest_frame
                    self.latest_frame=None
                if frame is not None:
                    image=Image.fromarray(frame)
                    w=max(2,self.preview_canvas.winfo_width())
                    h=max(2,self.preview_canvas.winfo_height())
                    iw,ih=image.size
                    factor=min(w/iw,h/ih)
                    size=(max(1,int(iw*factor)),max(1,int(ih*factor)))
                    if size!=image.size:image=image.resize(size,Image.Resampling.BILINEAR)
                    self.preview_photo=ImageTk.PhotoImage(image)
                    self.preview_canvas.delete('all')
                    self.preview_canvas.create_image(w//2,h//2,image=self.preview_photo,anchor='center')
                    self.preview_status.set(f'Vídeo ativo · {iw} × {ih} · FPS solicitado: {self.fps.get()} · {self.device.get()}')
        finally:
            self.after(50,self.show_frame)

    def save_snapshot(self):
        if Image is None:
            messagebox.showinfo('Imagem indisponível','Instale python3-pil e python3-pil.imagetk.')
            return
        # Um snapshot independente preserva a imagem em resolução de captura.
        with self.frame_lock:
            frame=self.snapshot_frame
            if frame is not None:frame=frame.copy()
        if frame is None:
            messagebox.showinfo('Sem imagem','Inicie o vídeo e aguarde a captura de um quadro.')
            return
        filename=filedialog.asksaveasfilename(defaultextension='.png',filetypes=[('Imagem PNG','*.png')],title='Salvar imagem da webcam')
        if filename:
            try:Image.fromarray(frame).save(filename)
            except Exception as exc:messagebox.showerror('Falha ao salvar',str(exc))
            else:self.preview_status.set('Imagem salva: '+filename)

    def close(self):
        self.stop_preview()
        self.destroy()

    def pick(self):
        path=filedialog.askopenfilename(title='Selecione o executável Anker')
        if path:self.binary.set(path)

    def queue(self,description,work,callback):
        if self.busy:return
        binary=self.binary.get().strip()
        device=self.device.get().strip()
        if not (Path(binary).is_file() and os.access(binary,os.X_OK)):
            messagebox.showerror('Executável não encontrado','Selecione o executável da ferramenta Anker.');return
        if not re.fullmatch(r'/dev/video\d+',device):
            messagebox.showerror('Dispositivo inválido','Informe um dispositivo como /dev/video0.');return
        self.busy=True
        self.refresh_btn.state(['disabled'])
        self.message.set(description)
        for c in self.controls.values():c.apply_btn.state(['disabled'])
        def worker():
            try:
                output=work(binary,device)
                self.after(0,lambda:self.complete(output,None,callback))
            except Exception as error:
                detail=str(error)
                self.after(0,lambda:self.complete(None,detail,callback))
        threading.Thread(target=worker,daemon=True).start()

    def complete(self,output,error,callback):
        self.busy=False
        self.refresh_btn.state(['!disabled'])
        if error:
            self.message.set('Falha: '+error)
            messagebox.showerror('Erro de comunicação',error)
        else:callback(output)
        self.dependencies()

    def dependencies(self):
        for key,c in self.controls.items():
            if not c.available:
                c.apply_btn.state(['disabled']);continue
            if key in self.inactive:
                c.field.state(['disabled']);c.apply_btn.state(['disabled'])
                c.status.set('Inativo (V4L2)')
                continue
            dependency=DEPENDENCIES.get(key)
            if dependency:
                parent,off_value=dependency
                parent_c=self.controls[parent]
                if parent_c.available and parent_c.value()==off_value:
                    c.field.state(['disabled']);c.apply_btn.state(['disabled'])
                    c.status.set('Modo automático')
                    continue
            if c.kind=='choice':c.field.configure(state='readonly')
            else:c.field.state(['!disabled'])
            c.apply_btn.state(['!disabled']);c.status.set('Disponível')

    def refresh(self):
        def work(binary,device):
            values,errors={},{}
            for key in SPECS:
                try:values[key]=cli(binary,device,'get',key)
                except Exception as exc:errors[key]=str(exc)
            inactive=set()
            v4l2=shutil.which('v4l2-ctl')
            if v4l2:
                try:
                    proc=subprocess.run([v4l2,'-d',device,'--list-ctrls-menus'],
                          capture_output=True,text=True,timeout=7)
                    if proc.returncode == 0:
                        for line in proc.stdout.splitlines():
                            m=re.match(r'^\s*([a-z][a-z0-9_]*)\s+0x[0-9a-f]+.*flags=([^\n]+)',line)
                            if m and 'inactive' in m.group(2).split(', '):inactive.add(m.group(1))
                except (OSError,subprocess.TimeoutExpired):pass
            return values,errors,inactive
        def done(result):
            values,errors,inactive=result
            self.inactive=inactive
            self.errors=errors
            for key,c in self.controls.items():
                if key in errors:c.disable(errors[key]);continue
                try:c.set_value(values[key]);c.enable()
                except (ValueError,TypeError) as exc:c.disable(str(exc));self.errors[key]=str(exc)
            self.message.set(f'{sum(c.available for c in self.controls.values())} controles acessíveis; '
                             f'{len(self.errors)} indisponíveis. '
                             + ('Detalhes: '+ '; '.join(f'{k}: {v}' for k,v in self.errors.items())[:280] if self.errors else ''))
        self.queue('Consultando os controles da webcam…',work,done)

    def apply_one(self,key,val):
        def work(binary,device):return cli(binary,device,'set',key,val)
        def done(output):
            control=self.controls[key]
            try:control.set_value(output);control.enable()
            except ValueError:pass
            self.message.set(f'{key} aplicado: {output}')
        self.queue(f'Aplicando {key} = {val}…',work,done)

    def save_profile(self):
        data={}
        for key,c in self.controls.items():
            if c.available:
                try:data[key]=c.value()
                except (TypeError,ValueError):pass
        PROFILE_DIR.mkdir(parents=True,exist_ok=True)
        filename=filedialog.asksaveasfilename(initialdir=str(PROFILE_DIR),defaultextension='.json',
            filetypes=[('Perfil JSON','*.json')],title='Salvar perfil')
        if filename:
            Path(filename).write_text(json.dumps({'model':'Anker PowerConf C200','controls':data},indent=2),encoding='utf-8')
            self.message.set('Perfil salvo: '+filename)

    def load_profile(self):
        filename=filedialog.askopenfilename(initialdir=str(PROFILE_DIR),filetypes=[('Perfil JSON','*.json')])
        if not filename:return
        try:
            payload=json.loads(Path(filename).read_text(encoding='utf-8'))
            values=payload['controls']
            if not isinstance(values,dict):raise ValueError('Perfil inválido')
            pending=[]
            for key,value in values.items():
                if key in self.controls and self.controls[key].available:
                    c=self.controls[key]
                    if c.kind=='slider':
                        lo,hi,step=c.options
                        n=int(value)
                        if n<lo or n>hi or (n-lo)%step:continue
                    elif c.kind=='choice' and str(value) not in c.options:continue
                    elif c.kind=='number':
                        n=int(value)
                        if not c.options[0]<=n<=c.options[1]:continue
                    pending.append((key,str(value)))
            if not pending:
                messagebox.showinfo('Perfil','Nenhum controle compatível está disponível.');return
        except (OSError,ValueError,KeyError,TypeError) as exc:
            messagebox.showerror('Perfil inválido',str(exc));return
        if not messagebox.askyesno('Aplicar perfil',f'Aplicar {len(pending)} configurações à webcam?'):
            return
        # Desabilitar automação antes de importar; escrever controles automáticos primeiro.
        def order(item):
            key=item[0]
            return (0 if key in ('white_balance_automatic','focus_automatic_continuous','auto_exposure') else 1)
        pending.sort(key=order)
        def work(binary,device):
            result,errors={},{}
            for key,val in pending:
                try:result[key]=cli(binary,device,'set',key,val)
                except Exception as exc:errors[key]=str(exc)
            return result,errors
        def done(out):
            results,errors=out
            for key,val in results.items():
                try:self.controls[key].set_value(val)
                except ValueError:pass
            self.message.set(f'Perfil aplicado: {len(results)} ajustes; {len(errors)} falhas.'+
                             (' '+ '; '.join(f'{k}: {v}' for k,v in errors.items())[:250] if errors else ''))
        self.queue('Aplicando perfil…',work,done)

if __name__=='__main__':
    Studio().mainloop()
