# Roteiro de testes do app — VagaCerta (MVP)

Testes manuais e simples para conferir se cada funcionalidade está funcionando.
Marque ✅ ou ❌ em cada item e anote o que aconteceu de diferente.

## Preparação

1. **API** (terminal 1), em `vagacerta/services/api`:
   ```bash
   .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **Painel do parceiro** (terminal 2), em `vagacerta/apps/web`: `npm run dev` → abrir http://localhost:3000
3. **App** (terminal 3), em `vagacerta/apps/mobile`: `npx expo start` e apertar `i` (simulador) ou ler o QR code (celular).

**Mudar a localização do simulador** (vários testes dependem disso). No menu do Simulator,
**Features → Location → Custom Location…**, ou no terminal:

```bash
xcrun simctl location booted set -25.4430,-49.2909   # Pátio Batel
```

| Local | Coordenada |
|---|---|
| Pátio Batel | `-25.4430,-49.2909` |
| R. Francisco Rocha × Av. do Batel (EstaR da Setran) | `-25.4430,-49.2890` |
| Estacionamento Demo Tiradentes (parceiro, Centro) | `-25.4305,-49.2705` |
| PUCPR (longe de tudo) | `-25.4515,-49.2507` |

**Simular outro usuário:** na tela **Levantamento (equipe)**, toque em "Trocar usuário de teste" (só aparece em desenvolvimento). O ID do usuário fica guardado no aparelho; recarregar o app não muda mais de usuário.

**Simular outro horário:** reinicie a API com, por exemplo, `VAGACERTA_AGORA=2026-10-23T22:00` (sexta 22h).

---

## 1. Mapa e busca

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 1.1 | Abrir o app | Mapa do Centro/Batel com linhas coloridas (ruas) e pinos (estacionamentos) | |
| 1.2 | Olhar as linhas do Batel | Linhas contínuas seguindo as ruas, em cores claras (estimativa) | |
| 1.3 | Digitar "guaira" na busca | Aparece "Teatro Guaíra" (a busca ignora acentos) | |
| 1.4 | Escolher "Shopping Pátio Batel" | Mapa aproxima do destino e mostra a lista de vagas recomendadas | |
| 1.5 | Escolher "Jardim Botânico" | Mensagem de que ainda não há vagas cadastradas perto (fora do piloto) | |
| 1.6 | Ver o rodapé | Legenda (cor clara = estimativa, cor forte = ao vivo), "+ Sugerir estacionamento" e o crédito do OpenStreetMap | |

## 2. Recomendação

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 2.1 | Destino Pátio Batel, **Lazer**, **1 h** | Lista mistura ruas e estacionamentos, cada um com regime ("Pode ser EstaR — confira a placa"), dificuldade e preço | |
| 2.2 | Trocar para **Trabalho**, **3 h** (em horário comercial) | Ruas com EstaR somem da lista: o EstaR permite no máximo 2 h | |
| 2.3 | Destino Praça Tiradentes, **IDOSO** | Aparece a vaga de idoso da R. Mal. Deodoro; sem credencial, ela não aparece | |
| 2.4 | Estacionamento do OSM na lista | Mostra "Preço não informado" | |
| 2.5 | Tocar em "Atualizar recomendação" | Lista recarrega sem erro | |

## 3. Disponibilidade (modelo sem dados ao vivo)

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 3.1 | Abrir uma vaga do Batel | Mostra "Fácil / Moderado / Difícil (estimativa)", sem porcentagem, e a explicação ("Terça, 15h · perto de …") | |
| 3.2 | API com `VAGACERTA_AGORA=2026-10-23T22:00` (sexta 22h) | No Batel aparecem bem mais trechos vermelhos/amarelos que verdes | |
| 3.3 | API com `VAGACERTA_AGORA=2026-10-25T07:00` (domingo 7h) | Quase tudo verde (fácil) | |
| 3.4 | Comparar cores | Sem dado ao vivo as cores são **claras**; com dado ao vivo (teste 8.2) ficam **fortes** | |

## 4. Tela da vaga

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 4.1 | Abrir uma vaga | Detalhes da estimativa vêm **fechados** | |
| 4.2 | Tocar em "Ver detalhes da estimativa ▾" | Abre fonte, "Como estimamos" e as barras de "Por que esta posição"; "Ocultar detalhes ▴" fecha | |
| 4.3 | Ver "Ir até a vaga" | Waze, Google Maps e Apple Maps (só no iPhone) numa linha só | |
| 4.4 | Tocar em cada botão de navegação | Abre o app (ou o site) com a rota até a vaga | |

## 5. Regra dos 300 m

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 5.1 | Localização na **PUCPR**; abrir uma vaga do Batel | "Você está a X km da vaga…" e os botões "Iniciar estacionamento", "Está livre/ocupada" e "Ajude a mapear" desativados | |
| 5.2 | Mudar para o **Pátio Batel** e tocar em "Atualizar minha posição" numa vaga a até 300 m | Botões liberados | |
| 5.3 | Simulador sem localização | Mensagem "Não consegui obter sua localização…" (sem erro técnico) | |

## 6. Estacionar (pagamento simulado)

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 6.1 | Perto da vaga, placa `ABC1D23`, "Iniciar estacionamento" | Abre a tela com contagem regressiva, placa e valor; pede permissão de notificação | |
| 6.2 | Placa `123` | Mensagem de placa inválida | |
| 6.3 | "Estender 30 min" | Hora de término e valor aumentam | |
| 6.4 | Estender além de 2 h numa vaga de EstaR | Mensagem de limite do EstaR | |
| 6.5 | Voltar ao mapa | Faixa "Estacionamento ativo até HH:MM · ver" no topo do painel | |
| 6.6 | "Encerrar e liberar a vaga" | Volta ao mapa; a vaga aparece como "Livre agora · vaga liberada por usuário" | |
| 6.7 | Sessão curta (ex.: 30 min) e esperar | Notificação "Seu estacionamento está acabando" 10 min antes do fim | |

## 7. Reportes e mapeamento colaborativo

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 7.1 | Perto de uma rua: "Está livre" | "Obrigado!"; a rua passa a mostrar "Livre agora · reporte de usuário", em cor forte (dado ao vivo) | |
| 7.2 | Repetir logo em seguida | Pede para aguardar (limite de 2 min) | |
| 7.3 | Numa rua do Batel: "Tem EstaR" | "Falta 1 confirmação de outros motoristas" | |
| 7.4 | Trocar usuário de teste e repetir "Tem EstaR" na mesma rua | "Mapa atualizado"; a tela da vaga mostra "EstaR · confirmado por usuários" (selo com borda contínua) | |
| 7.5 | Dois usuários marcam "Proibido estacionar" | Linha cinza e a rua sai das recomendações | |
| 7.6 | Num estacionamento do OSM: informar preço `12` | Passa a mostrar R$ 12,00/h ("informado por 1 usuário") | |
| 7.7 | Dois usuários: "Este estacionamento fechou" | O estacionamento some do mapa | |
| 7.8 | "+ Sugerir estacionamento": nome e preço, enviar | "Aparece no mapa quando mais 1 motorista confirmar" | |
| 7.9 | Trocar usuário de teste e sugerir de novo no mesmo lugar | "Já aparece no mapa"; novo pino no local | |
| 7.10 | "Chegou? Encontrou a vaga?" → Sim | "Obrigado!"; em http://localhost:8000/metricas a taxa de acerto muda | |

## 8. Estacionamentos parceiros (Centro, fictícios)

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 8.1 | Abrir "Estacionamento Demo Tiradentes" | Mostra "Estacionamento · parceiro VagaCerta" e botão "Reservar por 10 min"; sem "Ajude a mapear" | |
| 8.2 | No painel web, escolher "Parceiro Demo Centro" e informar 7 vagas na Garagem Demo Rui Barbosa | Em até 30 s o app mostra "7 vagas · atendente · há menos de 1 min" em cor forte | |
| 8.3 | Reservar no app | Código "VC-…" e validade de 10 min; o painel web mostra a reserva ativa | |
| 8.4 | Tentar uma segunda reserva | Mensagem de que já existe uma reserva ativa | |
| 8.5 | Abrir uma vaga de rua | Texto "Vagas de rua são espaço público e não podem ser reservadas" | |

## 9. Erros e situações-limite

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 9.1 | Parar a API e mexer no app | Mensagem "Não consegui falar com a API em …" (o app não trava) | |
| 9.2 | Subir a API de novo | App volta a funcionar em até 30 s; reportes, mapeamento, sessões e contagens **continuam lá** (banco SQLite) | |
| 9.3 | Negar a permissão de localização | Mensagem pedindo a permissão; o mapa continua funcionando | |

## 10. Funcionalidades novas

| # | Passos | Resultado esperado | ✅/❌ |
|---|---|---|---|
| 10.1 | Buscar "hospital são vicente" ou um endereço com número | Resultados reais de Curitiba (busca no OpenStreetMap), além dos destinos fixos | |
| 10.2 | Iniciar um estacionamento, fechar o Expo Go por completo e abrir de novo | Faixa "Estacionamento ativo até HH:MM" volta, com o tempo restante certo | |
| 10.3 | Abrir uma vaga, tocar em Waze/Google Maps/Apple Maps e voltar ao app a até 150 m da vaga | Pergunta "Chegou? Encontrou vaga em …?" (Sim / Não / Ainda não cheguei) | |
| 10.4 | Mesmo teste, voltando ao app longe da vaga | Não pergunta nada | |
| 10.5 | "Levantamento (equipe)" no rodapé do mapa | Lista as ruas a até 300 m, da mais próxima para a mais distante | |
| 10.6 | Digitar 3 em uma rua e tocar em "Contar" | Mapa mostra "3 vagas · contagem da equipe" em cor forte | |
| 10.7 | "Exportar CSV" | Baixa/abre a planilha com a contagem e a previsão do modelo no mesmo horário | |
| 10.8 | Reiniciar a API e abrir o CSV de novo | A contagem continua lá | |

---

## Testes automáticos (para quem mexer no código)

```bash
cd services/api && .venv/bin/python -m pytest          # API: regras, modelo, mapeamento, gerador do Batel
cd apps/mobile && npx tsc --noEmit && npx expo lint     # app: tipos e lint
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```
