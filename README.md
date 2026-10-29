# VagaCerta — MVP acadêmico (Fase 0)

Esqueleto do app de vagas de estacionamento em tempo real para Curitiba, seguindo o
[planejamento técnico](../Planejamento_Tecnico_VagaCerta.md).

> **Batel: dados reais. Centro: dados de demonstração.**
> - **Batel** — 205 trechos de rua (~3.660 vagas estimadas) e estacionamentos reais, gerados de dados abertos
>   (OpenStreetMap, IPPUC e lista de EstaR da Setran). Ver [Batel com dados reais](#batel-com-dados-reais).
> - **Centro** — trechos com traçado real, mas EstaR, capacidades e os estacionamentos parceiros ("Demo") são fictícios.
> - Em ambos, sem dado ao vivo a **disponibilidade** vem de um modelo com estabelecimentos reais do OSM
>   (bares, restaurantes, comércio...) e a fórmula de Erlang B, mostrado como "Fácil / Moderado / Difícil
>   (estimativa)". Os parâmetros ainda são suposições a calibrar — ver [services/ml/README.md](services/ml/README.md).
> - Nenhum pagamento é cobrado. Nada é publicado nas lojas: o app roda no **Expo Go**.

## Estrutura

```
vagacerta/
├── apps/mobile     # App do motorista — Expo SDK 58 + Expo Router + react-native-maps
                    #   (a versão do SDK precisa ser a mesma do Expo Go instalado no celular)
├── apps/web        # Painel do parceiro — Next.js 16
├── services/api    # API — Python 3.12 + FastAPI (monólito modular, dados em memória)
├── services/ml     # Notas e calibração do modelo de disponibilidade (v1 = estabelecimentos + Erlang B)
└── infra/          # PRÓXIMA FASE: PostGIS, Redis e OSRM (não usados pelo MVP)
```

## Como rodar

Pré-requisitos: Node 20+, Python 3.12 e o app **Expo Go** no celular.
O celular e o computador precisam estar **na mesma rede Wi-Fi**.

> Todos os comandos abaixo partem da pasta `vagacerta/` (a que contém este README).
> Se o terminal estiver em `Projeto de Negocio Inovador`, rode `cd vagacerta` antes.

**1. API** (terminal 1)

```bash
cd services/api
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa: http://localhost:8000/docs.
`--host 0.0.0.0` permite que o celular acesse a API; o macOS pode pedir para liberar no firewall.

**2. App do motorista** (terminal 2)

```bash
cd apps/mobile
npm install
npx expo start
```

Escaneie o QR code com o Expo Go (Android) ou com a câmera (iPhone).
O app encontra a API sozinho pelo IP do computador. Se não encontrar, crie
`apps/mobile/.env` com `EXPO_PUBLIC_API_URL=http://SEU_IP:8000`.

**3. Painel do parceiro** (terminal 3)

```bash
cd apps/web
npm install
npm run dev
```

Abra http://localhost:3000. Mude as vagas livres de um estacionamento e veja o app
do motorista mostrar "N vagas · atendente · há menos de 1 min" na próxima atualização (até 30 s).

### Dica para demonstrações

As regras do EstaR dependem do horário: depois das 19h e aos domingos a rua é grátis e
alguns estacionamentos fecham. Para apresentar em "horário comercial" a qualquer hora:

```bash
VAGACERTA_AGORA=2026-10-20T10:30 .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

O relógio da API começa nesse horário e avança normalmente.

**Regra dos 300 m.** Iniciar um estacionamento, reportar uma vaga e mapear (EstaR, preço,
estacionamento novo) só funcionam a até 300 m do local. Para demonstrar em sala, longe do Batel,
aumente o raio — o app lê esse valor da API:

```bash
VAGACERTA_DISTANCIA_MAX_M=20000 .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## O que o MVP já faz

| Funcionalidade | Onde |
|---|---|
| Busca de destino (lista mockada; Google Places depois) | `api/app/provedores/destinos.py` |
| Mapa com trechos de rua e estacionamentos coloridos pela chance de vaga | `mobile/src/app/index.tsx` |
| Recomendação por contexto (urgência, trabalho, lazer), duração e credencial (idoso/PCD) | `api/app/servicos/recomendacao.py` |
| Regras do EstaR: tempo máximo (2 h; 1 h na área calma), horário de cobrança, frações de 15 min | `api/app/servicos/regras.py` |
| Fusão de sinais com fonte e idade ("Livre agora · reporte de usuário · há 1 min") | `api/app/servicos/disponibilidade.py` |
| Sem dado ao vivo: demanda dos estabelecimentos do OSM por dia e hora + Erlang B ("Difícil (estimativa)") | `api/app/servicos/demanda.py` |
| Reserva de 10 min **só em parceiros**, com cota por estacionamento | `api/app/servicos/reservas.py` |
| Navegação pelo Waze, Google Maps ou Apple Maps (no iPhone), por deep link e sem custo de API | `mobile/src/lib/externos.ts` |
| Sessão com pagamento simulado, aviso local 10 min antes do fim, estender e encerrar | `mobile/src/app/sessao.tsx` |
| Encerrar sessão de rua avisa outros motoristas ("vaga liberada") | `api/app/servicos/sessoes.py` |
| Crowdsourcing "livre/ocupada" com antifraude simples (distância e intervalo) | `api/app/servicos/reportes.py` |
| Só inicia estacionamento a até 300 m da vaga (configurável) | `api/app/servicos/proximidade.py` |
| Linhas coloridas pela dificuldade (claras = estimativa, fortes = ao vivo); cinza para proibidos | `mobile/src/app/index.tsx` |
| Mapeamento colaborativo: "tem EstaR / sem EstaR / proibido", preço e fechamento de estacionamentos, sugestão de estacionamento novo (vale com 2 usuários concordando) | `api/app/servicos/mapeamento.py`, `mobile/src/app/sugerir.tsx` |
| "Encontrou a vaga?" → taxa de acerto; perguntado sozinho ao voltar ao app perto da vaga | `GET /metricas`, `mobile/src/componentes/Bastidores.tsx` |
| Ações dos usuários guardadas em SQLite e reaplicadas ao reiniciar a API | `api/app/persistencia.py` |
| ID anônimo guardado no aparelho; estacionamento ativo recuperado ao reabrir o app | `mobile/src/lib/api.ts` |
| Busca real de destinos em Curitiba (Photon/OpenStreetMap), com a lista fixa como reserva | `api/app/provedores/destinos.py` |
| Modo levantamento: contagem de vagas pela equipe e exportação CSV para calibrar o modelo | `mobile/src/app/levantamento.tsx`, `GET /levantamento/contagens.csv` |
| Painel do parceiro informando vagas livres ("Mágico de Oz") | `web/src/componentes/PainelParceiro.tsx` |

## Batel com dados reais

Gerado por `services/api/scripts/gerar_batel_osm.py` em `services/api/app/dados_osm/`:

| Dado | Fonte |
|---|---|
| Limite do bairro | IPPUC/GeoCuritiba — camada oficial "Divisa de Bairros" |
| Ruas, esquinas, mão única, faixas de pedestre, pontos de ônibus, hidrantes, entradas de garagem, faixas de ônibus e ciclofaixas | OpenStreetMap |
| Estacionamentos (só os de acesso público ou com nome) | OpenStreetMap |
| Trechos com EstaR | Lista da Setran publicada em 01/11/2019 (`scripts/batel_estar_setran_2019.json`) |

Como o OSM quase nunca diz onde se pode estacionar, vale a regra do CTB: **na rua pode, salvo
exceções**. Cada quadra (rua entre duas esquinas) vira um trecho com capacidade estimada: lados com
estacionamento (mão única = 1, mão dupla = 2, menos faixa de ônibus/ciclofaixa/proibição marcada),
menos 5 m em cada esquina, faixas de pedestre, pontos de ônibus, hidrantes e garagens mapeadas, e
25% a menos por garagens que não estão no mapa (fator a calibrar nas contagens de campo).
Quadras acima de 200 m viram partes de até 150 m.

| Regime | No app | Origem |
|---|---|---|
| EstaR (Setran: implantado) | selo contínuo "EstaR" | lista da Setran |
| EstaR previsto | selo tracejado, "confira a placa" | lista da Setran ("próximos meses") |
| A confirmar | selo tracejado, "Pode ser EstaR — confira a placa" | demais quadras; usa as regras do EstaR por cautela |
| Confirmado por usuários | selo contínuo, "confirmado por usuários" | 2 usuários concordando no mapeamento colaborativo |
| Proibido | cinza, fora da recomendação | mapeamento colaborativo |

Não existe camada de EstaR no GeoCuritiba nem no portal de dados abertos; a lista da Setran é a única
fonte pública encontrada (3 trechos implantados e 8 previstos — 3 dos previstos não fecham no OSM e
são ignorados com aviso). Estacionamentos do OSM não têm preço nem horário: o app mostra
"preço não informado" até os usuários informarem.

```bash
cd services/api
.venv/bin/python scripts/gerar_batel_osm.py            # usa o cache local se existir
.venv/bin/python scripts/gerar_batel_osm.py --baixar   # baixa de novo do IPPUC e do OSM
```

O resumo da geração (fontes, contagens, quadras excluídas) fica em `app/dados_osm/batel_metadados.json`.

Os estabelecimentos usados pelo modelo de disponibilidade (Centro e Batel) vêm de outro script:

```bash
.venv/bin/python scripts/baixar_pois_osm.py   # grava app/dados_osm/pois.json
```

## Trechos de rua do Centro (OpenStreetMap)

O traçado das vagas de rua do Centro também vem do OpenStreetMap. A equipe descreve cada trecho como
**"rua X, entre Y e Z"** em `services/api/scripts/trechos_referencia.json` (nomes exatamente
como no OSM, com tipo e capacidade levantados na rua), e o script gera `app/dados_mock/trechos.json`:

```bash
cd services/api
.venv/bin/python scripts/importar_trechos_osm.py --esquinas "Rua Cruz Machado"  # ver as esquinas de uma rua
.venv/bin/python scripts/importar_trechos_osm.py                                # gerar trechos.json
```

O script recusa trechos que atravessam mais de uma quadra, que caem em calçadão ou cujas ruas
não se cruzam; tira 5 m de cada esquina (CTB) e posiciona vagas de idoso/PCD/carga junto à esquina indicada.
O OSM **não diz onde existe EstaR** nem quantas vagas há — isso vem do levantamento de campo.
Dados © colaboradores do OpenStreetMap (licença ODbL): o crédito aparece no app.

## Verificações

Roteiro de testes manuais do app: [docs/ROTEIRO_DE_TESTES.md](docs/ROTEIRO_DE_TESTES.md).
O GitHub Actions roda as mesmas verificações a cada push (`.github/workflows/ci.yml`).
Para hospedar a API na nuvem: [docs/HOSPEDAGEM.md](docs/HOSPEDAGEM.md).

```bash
cd services/api && .venv/bin/python -m pytest      # 70 testes
cd apps/mobile && npx tsc --noEmit && npx expo lint
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```

## Próximos passos

1. **Mapa do Google no app:** criar chaves restritas e configurar o plugin `react-native-maps`
   no `app.json`; exige *development build* (`npx expo run:android`). No Expo Go o mapa funciona sem chave.
2. **Busca com Google:** `DestinosGooglePlaces` (Places API New com session token), se o Photon não bastar.
3. **Banco:** `CatalogoPostgres` sobre `infra/db/schema.sql`.
4. **Rotas reais:** `RotasOSRM` (ver `infra/README.md`).
5. **Login:** Supabase Auth; a API passa a validar o JWT em vez do cabeçalho `X-Usuario-Id`.
6. **Tipos compartilhados:** gerar `apps/*/src/lib/tipos.ts` do OpenAPI (`openapi-typescript`).
7. **Contagens de campo no Batel:** conferir o EstaR quadra a quadra e calibrar o fator de garagens
   (hoje 0,75) e os parâmetros do modelo de demanda (ver `services/ml/README.md`).
8. **Hospedar a API** (ver `docs/HOSPEDAGEM.md`) e adicionar login ao painel do parceiro.
