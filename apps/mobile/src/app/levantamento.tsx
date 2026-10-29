import * as Linking from 'expo-linking';
import { useEffect, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Botao } from '@/componentes/Botao';
import { api, carregarUsuario } from '@/lib/api';
import { useApp } from '@/lib/estado';
import { posicaoAtual } from '@/lib/externos';
import { cores, distanciaAteLinha, metros } from '@/lib/formato';
import { RAIO_VAGAS_M, REGIAO_PILOTO } from '@/lib/regiao';
import type { Coordenada, VagaNoMapa } from '@/lib/tipos';

/**
 * Modo levantamento (para a equipe): percorrer as ruas contando vagas livres e conferindo
 * a placa. Cada contagem vira dado ao vivo no mapa e vai para o CSV de calibração do modelo.
 */
export default function TelaLevantamento() {
  const { vagas, setVagas, distanciaMaximaM } = useApp();
  const [posicao, setPosicao] = useState<Coordenada | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [contagens, setContagens] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [registradas, setRegistradas] = useState(0);

  useEffect(() => {
    posicaoAtual()
      .then(setPosicao)
      .catch((e: Error) => setErro(e.message));
  }, []);

  const proximas = posicao
    ? vagas
        .filter((v): v is VagaNoMapa & { coordenadas: [number, number][] } => v.tipo === 'rua' && !!v.coordenadas)
        .map((v) => ({ vaga: v, distancia: distanciaAteLinha(posicao, v.coordenadas) }))
        .filter((x) => x.distancia <= distanciaMaximaM)
        .sort((a, b) => a.distancia - b.distancia)
    : [];

  async function executar(chave: string, acao: () => Promise<void>) {
    setOcupado(chave);
    try {
      await acao();
    } catch (e) {
      Alert.alert('Não deu certo', (e as Error).message);
    } finally {
      setOcupado(null);
    }
  }

  const atualizarPosicao = () =>
    executar('posicao', async () => {
      setErro(null);
      setPosicao(await posicaoAtual());
    });

  const recarregarMapa = () =>
    api.vagas(REGIAO_PILOTO.latitude, REGIAO_PILOTO.longitude, RAIO_VAGAS_M).then(setVagas).catch(() => {});

  const contar = (vaga: VagaNoMapa) =>
    executar(`contar-${vaga.id}`, async () => {
      const texto = contagens[vaga.id] ?? '';
      const numero = Number(texto);
      if (texto === '' || !Number.isInteger(numero) || numero < 0) throw new Error('Digite quantas vagas livres você vê.');
      const atual = await posicaoAtual();
      setPosicao(atual);
      const r = await api.contarVagas(vaga.id, numero, atual);
      setRegistradas(r.total_de_contagens);
      setContagens((c) => ({ ...c, [vaga.id]: '' }));
      await recarregarMapa();
    });

  const mapear = (vaga: VagaNoMapa, tipo: 'tem_estar' | 'sem_estar' | 'proibido') =>
    executar(`${tipo}-${vaga.id}`, async () => {
      const r = await api.mapearTrecho(vaga.id, tipo, await posicaoAtual());
      if (r.aplicado) await recarregarMapa();
      Alert.alert('Registrado', r.mensagem);
    });

  const trocarUsuario = async () => {
    const id = await carregarUsuario(true);
    Alert.alert('Usuário de teste trocado', `Agora você é ${id}. Útil para simular a confirmação de outro motorista.`);
  };

  return (
    <ScrollView contentContainerStyle={estilos.conteudo} keyboardShouldPersistTaps="handled">
      <Text style={estilos.suave}>
        Para a equipe: em cada rua a até {metros(distanciaMaximaM)}, conte as vagas livres agora e confira a placa.
        As contagens viram dado ao vivo no mapa e servem para calibrar o modelo.
      </Text>
      {erro && <Text style={estilos.aviso}>{erro}</Text>}
      {registradas > 0 && <Text style={estilos.ok}>{registradas} contagens registradas no total.</Text>}
      <View style={estilos.linha}>
        <Botao titulo="Atualizar posição" variante="secundario" carregando={ocupado === 'posicao'} onPress={atualizarPosicao} />
        <Botao titulo="Exportar CSV" variante="secundario" onPress={() => Linking.openURL(api.urlExportarContagens())} />
      </View>

      {posicao && proximas.length === 0 && (
        <Text style={estilos.suave}>Nenhuma rua mapeada por perto. Vá até o Batel ou o Centro.</Text>
      )}

      {proximas.map(({ vaga, distancia }) => (
        <View key={vaga.id} style={estilos.cartao}>
          <Text style={estilos.nome}>{vaga.nome}</Text>
          <Text style={estilos.suave}>
            {metros(distancia)} daqui · {vaga.rotulo_regime} · ~{vaga.capacidade} vagas
          </Text>
          <View style={estilos.linha}>
            <TextInput
              value={contagens[vaga.id] ?? ''}
              onChangeText={(t) => setContagens((c) => ({ ...c, [vaga.id]: t.replace(/\D/g, '') }))}
              keyboardType="number-pad"
              placeholder="Vagas livres"
              style={[estilos.campo, { flex: 1 }]}
            />
            <Botao titulo="Contar" carregando={ocupado === `contar-${vaga.id}`} onPress={() => contar(vaga)} />
          </View>
          <View style={estilos.linha}>
            <Botao compacto variante="secundario" titulo="Tem EstaR" carregando={ocupado === `tem_estar-${vaga.id}`} onPress={() => mapear(vaga, 'tem_estar')} />
            <Botao compacto variante="secundario" titulo="Grátis" carregando={ocupado === `sem_estar-${vaga.id}`} onPress={() => mapear(vaga, 'sem_estar')} />
            <Botao compacto variante="secundario" titulo="Proibido" carregando={ocupado === `proibido-${vaga.id}`} onPress={() => mapear(vaga, 'proibido')} />
          </View>
        </View>
      ))}

      {__DEV__ && (
        <View style={estilos.linha}>
          <Botao titulo="Trocar usuário de teste" variante="secundario" onPress={trocarUsuario} />
        </View>
      )}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  conteudo: { padding: 16, gap: 12, paddingBottom: 40, backgroundColor: cores.fundo },
  suave: { fontSize: 13, color: cores.suave },
  aviso: { fontSize: 14, color: cores.talvez },
  ok: { fontSize: 14, color: cores.livre, fontWeight: '600' },
  linha: { flexDirection: 'row', gap: 8 },
  cartao: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  nome: { fontSize: 15, fontWeight: '700', color: cores.texto },
  campo: { borderWidth: 1, borderColor: cores.borda, borderRadius: 10, paddingHorizontal: 12, minHeight: 46, fontSize: 16, color: cores.texto },
});
