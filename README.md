<div align="center">

# ⚡ InstalockValorant

**Instalock automático para Valorant — rápido, limpo e sem injeção de memória.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Valorant](https://img.shields.io/badge/Valorant-API-FF4655?style=flat-square)](https://playvalorant.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4?style=flat-square&logo=windows)](https://microsoft.com)
[![Site](https://img.shields.io/badge/Site-instalockvalorant.vercel.app-FF4655?style=flat-square&logo=vercel&logoColor=white)](https://instalockvalorant.vercel.app)

### 🌐 [instalockvalorant.vercel.app](https://instalockvalorant.vercel.app)

</div>

---

## 📋 Sobre o Projeto

InstalockValorant é uma ferramenta desktop que **seleciona e trava automaticamente** seu agente preferido assim que a fase de seleção começa — antes que qualquer outro jogador possa pegá-lo.

Utiliza a **API local oficial do Riot Client** via [valclient.py](https://github.com/colinhartigan/valclient.py), sem modificação de memória ou injeção de processo.

---

## 📥 Download

> **A forma mais fácil de baixar é pelo site oficial:**
>
> ### 👉 [instalockvalorant.vercel.app](https://instalockvalorant.vercel.app)

Ou acesse direto a seção de [Releases](../../releases) deste repositório.

---

## ✨ Funcionalidades

- 🎯 **Instalock automático** — detecta a fase de seleção e trava em milissegundos
- 🗺️ **Agente por mapa** — configure um agente diferente para cada mapa
- 🖼️ **Grid visual com ícones oficiais** dos agentes (buscados direto da Riot API)
- 🌍 **Detecção automática de região** via log do próprio jogo
- 🔑 **Hotkey global configurável** (padrão: `F1`) — funciona mesmo com o jogo em foco
- 💾 **Configuração persistente** — lembra seu agente e hotkey entre sessões
- 🔍 **Diagnóstico integrado** — botão "Testar" para debugar a conexão em tempo real
- 🎨 **UI dark theme** estilo Valorant (CustomTkinter)
- 📦 **Executável standalone** — sem precisar de Python instalado

---

## ⚠️ Aviso

> Esta ferramenta usa exclusivamente a **API local** exposta pelo Riot Client e **não modifica memória, arquivos do jogo ou processos**. Ainda assim, pode violar os Termos de Serviço da Riot Games. **Use por conta e risco.** Recomendado apenas para uso pessoal.

---

## 🖥️ Requisitos

Para **usar o executável** (usuário final):
- Windows 10 ou 11
- Valorant instalado e logado
- Conexão com a internet (apenas na 1ª execução para baixar ícones dos agentes)

Para **compilar do código-fonte** (desenvolvedor):
- Python 3.11+
- Git
- Conexão com a internet

---

## 🚀 Como Usar (Executável)

1. Baixe o `InstalockValorant.exe` em **[instalockvalorant.vercel.app](https://instalockvalorant.vercel.app)**
2. Abra o **Valorant** e aguarde o menu principal carregar
3. Execute o `InstalockValorant.exe`
   > Na **primeira execução**: o programa baixa os ícones dos agentes (~30 segundos)
4. Aguarde a status bar mostrar: `✅ Conectado | Região: BR`
5. **Selecione o mapa** no painel esquerdo (ou deixe em Padrão)
6. **Clique no agente** que deseja para aquele mapa
7. Pressione **F1** para ativar (badge fica verde: `● ATIVO`)
8. Entre na fila — ao abrir a seleção de agentes, o lock acontece instantaneamente

### Dica
> Ative o instalock **antes de aceitar a partida** para garantir máxima velocidade.

---

## 🛠️ Como Compilar (Desenvolvedores)

### 1. Clone o repositório
```bash
git clone https://github.com/DevAlex-full/InstalockValorant.git
cd InstalockValorant
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Compile o executável
```bash
.\build.bat
```

O arquivo `InstalockValorant.exe` será gerado na raiz do projeto.  
**O `.exe` é standalone** — quem baixar não precisa ter Python instalado.

---

## 📁 Estrutura do Projeto

```
InstalockValorant/
├── assets/
│   ├── instalock_logo.png    # Logo oficial
│   ├── instalock_logo.ico    # Ícone para o .exe
│   └── make_ico.py           # Script para gerar o .ico
├── src/
│   ├── main.py               # UI principal (CustomTkinter) + lógica de poll
│   ├── valorant_api.py       # Integração com a API do Valorant via valclient
│   └── agents.py             # Busca e cache de agentes + mapas (valorant-api.com)
├── requirements.txt          # Dependências Python
├── build.bat                 # Script de compilação → .exe standalone
└── README.md
```

---

## ⚙️ Como Funciona (Técnico)

```
1. Lê o ShooterGame.log do Valorant para detectar a região real do servidor

2. Inicializa o valclient com a região correta
   → Autentica via lockfile local (porta + senha Basic auth)
   → Obtém Bearer token + Entitlement JWT

3. Poll a cada 150ms via fetch_presence():
   → sessionLoopState == "PREGAME" → fase de seleção detectada!

4. Detecta o mapa atual via pregame_fetch_match()
   → Usa o agente configurado para aquele mapa
   → Fallback para o agente padrão se não houver configuração

5. Executa o instalock sem delay:
   → pregame_select_character(agent_id)  ← select
   → pregame_lock_character(agent_id)    ← trava definitivo 🔒

6. Hotkey global via pynput (sem privilégios de admin)
```

---

## 📦 Dependências

| Lib | Uso |
|---|---|
| [valclient.py](https://github.com/colinhartigan/valclient.py) | API oficial do Valorant |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | UI dark theme moderna |
| [Pillow](https://python-pillow.org/) | Renderização de ícones dos agentes |
| [pynput](https://pynput.readthedocs.io/) | Hotkey global |
| [requests](https://requests.readthedocs.io/) | Download de ícones via valorant-api.com |
| [PyInstaller](https://pyinstaller.org/) | Compilação para .exe standalone |

---

## 🤝 Contribuindo

Pull requests são bem-vindos! Para mudanças maiores, abra uma issue primeiro.

```bash
git checkout -b feature/minha-feature
git commit -m "feat: adiciona minha feature"
git push origin feature/minha-feature
```

---

## 📄 Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE) para mais informações.

---

<div align="center">

Desenvolvido por [@DevAlex-full](https://github.com/DevAlex-full)

**🌐 [instalockvalorant.vercel.app](https://instalockvalorant.vercel.app)**

</div>
