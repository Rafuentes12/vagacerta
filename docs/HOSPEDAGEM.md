# Hospedar a API na nuvem

Com a API online, o app funciona em qualquer rede (inclusive 5G) sem depender do
computador de ninguém. O app continua rodando pelo Expo Go; só a API muda de lugar.

A API guarda as ações dos usuários num arquivo SQLite, então o serviço precisa de um
**disco persistente**. O Fly.io oferece isso no plano gratuito (volume de até 3 GB).

## Fly.io (recomendado)

1. Instale e entre na conta:
   ```bash
   brew install flyctl
   fly auth signup        # ou: fly auth login
   ```
2. Em `services/api`, crie o app (sem fazer deploy ainda):
   ```bash
   fly launch --no-deploy --name vagacerta-api --region gru
   ```
3. Crie o volume do banco e monte em `/dados` — acrescente ao `fly.toml` gerado:
   ```toml
   [mounts]
     source = "dados"
     destination = "/dados"
   ```
   ```bash
   fly volumes create dados --size 1 --region gru
   ```
4. Publique:
   ```bash
   fly deploy
   ```
5. Teste: `https://vagacerta-api.fly.dev/saude` deve responder `"persistencia": true`.

## Apontar o app e o painel para a API online

- App: `apps/mobile/.env` com `EXPO_PUBLIC_API_URL=https://vagacerta-api.fly.dev` e reinicie com `npx expo start --clear`.
- Painel: `apps/web/.env.local` com `NEXT_PUBLIC_API_URL=https://vagacerta-api.fly.dev`.

## Antes de deixar público

- O painel do parceiro ainda não tem login: qualquer pessoa com o endereço pode alterar as vagas
  dos estacionamentos fictícios. Para testes da equipe tudo bem; para usuários reais, adicionar login.
- A busca de destinos usa o Photon (photon.komoot.io), que é gratuito para uso moderado.
