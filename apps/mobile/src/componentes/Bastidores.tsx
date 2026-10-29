import { useEffect, useRef } from 'react';
import { Alert, AppState } from 'react-native';

import { api } from '@/lib/api';
import { useApp } from '@/lib/estado';
import { posicaoAtual } from '@/lib/externos';
import { distanciaAteLinha, distanciaKm } from '@/lib/formato';

const RAIO_CHEGADA_M = 150;
const VALIDADE_NAVEGACAO_MS = 3 * 60 * 60 * 1000;

/** Ao abrir o app, recupera o estacionamento que estava ativo (a API guarda as sessões). */
export function RestauradorDeSessao() {
  const { setSessaoLocal } = useApp();

  useEffect(() => {
    Promise.all([api.sessaoAtiva(), api.saude()])
      .then(([sessao, saude]) => {
        if (!sessao) return;
        // A contagem regressiva usa o relógio do celular; descontamos o tempo já decorrido na API.
        const decorrido = Date.parse(saude.agora) - Date.parse(sessao.inicio);
        setSessaoLocal({ sessao, inicioLocal: Date.now() - decorrido, avisoId: null });
      })
      .catch(() => {});
  }, [setSessaoLocal]);

  return null;
}

/**
 * Depois de abrir o Waze/Google Maps/Apple Maps, quando o motorista volta para o app perto
 * da vaga, pergunta se ele encontrou a vaga. É a métrica de acerto do planejamento, sem
 * depender de a pessoa lembrar de tocar no botão.
 */
export function DetectorDeChegada() {
  const { navegacao, setNavegacao } = useApp();
  const atual = useRef(navegacao);

  useEffect(() => {
    atual.current = navegacao;
  }, [navegacao]);

  useEffect(() => {
    const assinatura = AppState.addEventListener('change', async (estado) => {
      const nav = atual.current;
      if (estado !== 'active' || !nav) return;
      if (Date.now() - nav.desde > VALIDADE_NAVEGACAO_MS) {
        setNavegacao(null);
        return;
      }
      const posicao = await posicaoAtual().catch(() => null);
      if (!posicao) return;
      const distancia = nav.coordenadas
        ? distanciaAteLinha(posicao, nav.coordenadas)
        : distanciaKm(posicao, nav) * 1000;
      if (distancia > RAIO_CHEGADA_M) return;

      const responder = (encontrou: boolean) => {
        setNavegacao(null);
        api.avaliarChegada(nav.vagaId, encontrou).catch(() => {});
      };
      Alert.alert('Chegou?', `Encontrou vaga em ${nav.nome}?`, [
        { text: 'Ainda não cheguei', style: 'cancel' },
        { text: 'Não', onPress: () => responder(false) },
        { text: 'Sim', onPress: () => responder(true) },
      ]);
    });
    return () => assinatura.remove();
  }, [setNavegacao]);

  return null;
}
