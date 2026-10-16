# Anker C200 Studio

Painel gráfico **não oficial** para a webcam **Anker PowerConf C200**, em Ubuntu AMD64.

## Funcionalidades

- Preview de vídeo em tempo real (OpenCV + V4L2).
- Sliders para brilho, contraste, saturação, gama, nitidez, zoom, pan, tilt e foco.
- Controles de FOV, HDR, espelhamento, balanço de branco e exposição.
- Resolução/FPS negociados com o hardware; perfis JSON e tratamento de controles indisponíveis.

## Instalação

Baixe o arquivo `.deb` em **Releases** e instale:

```bash
sudo apt install ./anker-c200-studio_0.5.0_amd64.deb
anker-c200-studio
```

O controlador está **incluído**: você não precisa instalar o Linux Tools manualmente. As dependências Python/Tkinter/OpenCV são resolvidas pelo APT.

Diagnóstico:

```bash
lsusb -d 291a:3369
v4l2-ctl --list-devices
anker-c200-tools --device /dev/video0 get fov
```

## Compilar pacote

Ubuntu/Debian AMD64 com `dpkg-deb`:

```bash
bash scripts/build-deb.sh
```

O resultado fica em `dist/`. Pushes na `main` geram artefatos; tags `v0.5.0` geram releases automaticamente com o `.deb`.

## Estrutura

- `src/app.py`: interface Tkinter.
- `vendor/anker-powerconf-c200-linux-tools`: **binário AMD64 pré-compilado** do controlador original, e não seu código-fonte.
- `vendor/LICENSE`: licença MIT do controlador.
- `packaging/`: entrada no menu de aplicativos.
- `scripts/build-deb.sh`: empacotamento.
- `.github/workflows/build.yml`: CI e Release.

## Créditos e licenças

Interface: MIT (`LICENSE`). Controlador: projeto [erans/anker-powerconf-c200-linux-tools](https://github.com/erans/anker-powerconf-c200-linux-tools) por Eran Sandler, MIT (`vendor/LICENSE`). Para revisar ou recompilar o controlador, consulte o upstream. O projeto não é afiliado à Anker.

## Desinstalação

```bash
sudo apt remove anker-c200-studio
```

Perfis do usuário em `~/.config/anker-c200-studio/profiles/` não são excluídos.
