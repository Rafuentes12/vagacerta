import * as Notifications from 'expo-notifications';
import { Stack, router } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';

import { DetectorDeChegada, RestauradorDeSessao } from '@/componentes/Bastidores';
import { carregarUsuario } from '@/lib/api';
import { ProvedorEstado } from '@/lib/estado';
import { cores } from '@/lib/formato';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export default function Layout() {
  // O ID do usuário (guardado no aparelho) precisa estar carregado antes da primeira chamada à API.
  const [pronto, setPronto] = useState(false);
  useEffect(() => {
    carregarUsuario().finally(() => setPronto(true));
  }, []);

  // Tocar no aviso de expiração abre a tela da sessão.
  useEffect(() => {
    const assinatura = Notifications.addNotificationResponseReceivedListener((resposta) => {
      const rota = resposta.notification.request.content.data?.rota;
      if (rota === '/sessao') router.push('/sessao');
    });
    return () => assinatura.remove();
  }, []);

  if (!pronto) return null;

  return (
    <ProvedorEstado>
      <RestauradorDeSessao />
      <DetectorDeChegada />
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerTintColor: cores.marinho,
          headerTitleStyle: { fontWeight: '700' },
          headerBackTitle: 'Voltar',
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="vaga/[id]" options={{ title: 'Vaga' }} />
        <Stack.Screen name="sessao" options={{ title: 'Estacionamento ativo' }} />
        <Stack.Screen name="sugerir" options={{ title: 'Sugerir estacionamento' }} />
        <Stack.Screen name="levantamento" options={{ title: 'Levantamento de campo' }} />
      </Stack>
    </ProvedorEstado>
  );
}
