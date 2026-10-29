import { Stack, router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Botao } from '@/componentes/Botao';
import { api } from '@/lib/api';
import { duracaoMs, useApp } from '@/lib/estado';
import { abrirNavegacao, agendarAvisoDeExpiracao, posicaoAtual } from '@/lib/externos';
import { cores, corDoEstado, distanciaAteLinha, distanciaKm, hora, metros, reais } from '@/lib/formato';
import { RAIO_VAGAS_M, REGIAO_PILOTO } from '@/lib/regiao';
import type { Coordenada, Estimativa } from '@/lib/tipos';

const NOMES_COMPONENTES: Record<string, string> = {
  prob_livre: 'Chance de vaga',
  preco: 'Preço',
  caminhada: 'Caminhada',
  tempo_carro: 'Tempo de carro',
  confianca: 'Confiança do dado',
};

export default function TelaVaga() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const {
    recomendacao, vagas, setVagas, reserva, setReserva, sessaoLocal, setSessaoLocal, distanciaMaximaM, iniciarNavegacao,
  } = useApp();
  const [placa, setPlaca] = useState('ABC1D23');
  const [preco, setPreco] = useState('');
  const [detalhesAbertos, setDetalhesAbertos] = useState(false);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [posicao, setPosicao] = useState<Coordenada | null>(null);
  const [erroPosicao, setErroPosicao] = useState<string | null>(null);

  // Onde o usuário está: algumas ações só valem perto da vaga.
  useEffect(() => {
    posicaoAtual()
      .then(setPosicao)
      .catch((e: Error) => setErroPosicao(e.message));
  }, []);

  const candidato = recomendacao?.candidatos.find((c) => c.id === id);
  const vaga = candidato ?? vagas.find((v) => v.id === id);
  if (!vaga) {
    return (
      <View style={estilos.vazio}>
        <Text style={estilos.texto}>Vaga não encontrada.</Text>
      </View>
    );
  }

  const ehRua = vaga.tipo === 'rua';
  const reservaDestaVaga = reserva?.estacionamento_id === vaga.id && reserva.status === 'ativa' ? reserva : null;
  const duracao = recomendacao?.duracao_min ?? 60;
  const distancia =
    posicao === null
      ? null
      : vaga.coordenadas
        ? distanciaAteLinha(posicao, vaga.coordenadas)
        : distanciaKm(posicao, vaga) * 1000;
  const perto = distancia !== null && distancia <= distanciaMaximaM;
  const podeMapear = !vaga.parceiro; // dados de parceiros vêm deles mesmos

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

  // Pega a posição de novo na hora da ação (a API confere a distância).
  async function posicaoFresca(): Promise<Coordenada> {
    const atual = await posicaoAtual();
    setPosicao(atual);
    return atual;
  }

  const atualizarPosicao = () =>
    executar('posicao', async () => {
      setErroPosicao(null);
      await posicaoFresca();
    });

  const recarregarMapa = () =>
    api.vagas(REGIAO_PILOTO.latitude, REGIAO_PILOTO.longitude, RAIO_VAGAS_M).then(setVagas).catch(() => {});

  // Guarda para onde o motorista foi: ao voltar ao app perto da vaga, perguntamos "Encontrou?".
  const navegar = (app: 'waze' | 'google' | 'apple') => {
    iniciarNavegacao({ vagaId: vaga.id, nome: vaga.nome, lat: vaga.lat, lng: vaga.lng, coordenadas: vaga.coordenadas });
    abrirNavegacao(app, vaga.lat, vaga.lng);
  };

  const reservar = () =>
    executar('reserva', async () => {
      setReserva(await api.reservar(vaga.id));
    });

  const cancelarReserva = () =>
    executar('reserva', async () => {
      if (reservaDestaVaga) setReserva(await api.cancelarReserva(reservaDestaVaga.id));
    });

  const iniciarSessao = () =>
    executar('sessao', async () => {
      const sessao = await api.iniciarSessao(vaga.id, placa, duracao, await posicaoFresca());
      const inicioLocal = Date.now();
      const avisoId = await agendarAvisoDeExpiracao(new Date(inicioLocal + duracaoMs(sessao)));
      setSessaoLocal({ sessao, inicioLocal, avisoId });
      router.replace('/sessao');
    });

  const reportar = (livre: boolean) =>
    executar(livre ? 'livre' : 'ocupada', async () => {
      await api.reportar(vaga.id, livre, await posicaoFresca());
      Alert.alert('Obrigado!', 'Seu reporte ajuda outros motoristas nos próximos minutos.');
    });

  const mapearTrecho = (tipo: 'tem_estar' | 'sem_estar' | 'proibido') =>
    executar(tipo, async () => {
      const r = await api.mapearTrecho(vaga.id, tipo, await posicaoFresca());
      if (r.aplicado) await recarregarMapa();
      Alert.alert('Obrigado!', r.mensagem);
    });

  const informarPreco = () =>
    executar('preco', async () => {
      const valor = Number(preco.replace(',', '.'));
      if (!preco || Number.isNaN(valor)) throw new Error('Digite o preço por hora, por exemplo 12,50.');
      const r = await api.informarPreco(vaga.id, valor, await posicaoFresca());
      await recarregarMapa();
      setPreco('');
      Alert.alert('Obrigado!', r.mensagem);
    });

  const informarFechado = () =>
    executar('fechado', async () => {
      const r = await api.informarFechado(vaga.id, await posicaoFresca());
      if (r.aplicado) {
        await recarregarMapa();
        router.back();
      }
      Alert.alert('Obrigado!', r.mensagem);
    });

  const avaliarChegada = (encontrou: boolean) =>
    executar(encontrou ? 'sim' : 'nao', async () => {
      await api.avaliarChegada(vaga.id, encontrou);
      Alert.alert('Obrigado!', 'Isso entra na nossa taxa de acerto.');
    });

  const avisoDistancia = erroPosicao
    ? erroPosicao
    : distancia === null
      ? 'Verificando sua localização…'
      : `Você está a ${metros(distancia)} da vaga. Para isso, chegue a até ${metros(distanciaMaximaM)}.`;

  return (
    <ScrollView contentContainerStyle={estilos.conteudo}>
      <Stack.Screen options={{ title: ehRua ? 'Vaga de rua' : 'Estacionamento' }} />

      <Text style={estilos.titulo}>{vaga.nome}</Text>
      <View style={[estilos.selo, vaga.tracejado && estilos.seloTracejado]}>
        <Text style={estilos.seloTexto}>{vaga.rotulo_regime}</Text>
      </View>
      <View style={[estilos.estado, { borderLeftColor: corDoEstado(vaga.estado) }]}>
        <Text style={estilos.estadoRotulo}>{vaga.estado.rotulo}</Text>
        {vaga.estado.ao_vivo ? (
          <Text style={estilos.suave}>
            Chance de vaga: {Math.round(vaga.estado.prob_livre * 100)}% · confiança{' '}
            {Math.round(vaga.estado.confianca * 100)}%
          </Text>
        ) : (
          <Text style={estilos.suave}>
            Sem dado ao vivo: estimativa pelo horário e pelos estabelecimentos por perto.
          </Text>
        )}
        {vaga.estado.explicacao && <Text style={estilos.suave}>{vaga.estado.explicacao}</Text>}
      </View>

      <View style={estilos.bloco}>
        <Text style={estilos.texto}>
          {vaga.capacidade_estimada ? '~' : ''}
          {vaga.capacidade} vagas{vaga.capacidade_estimada ? ' (estimativa)' : ''}
        </Text>
        <Pressable onPress={() => setDetalhesAbertos((aberto) => !aberto)} hitSlop={8} accessibilityRole="button">
          <Text style={estilos.link}>{detalhesAbertos ? 'Ocultar detalhes ▴' : 'Ver detalhes da estimativa ▾'}</Text>
        </Pressable>
        {detalhesAbertos && (
          <>
            <Text style={estilos.suave}>Fonte: {vaga.fonte}</Text>
            {vaga.estimativa && <TextoEstimativa estimativa={vaga.estimativa} />}
            {candidato && (
              <>
                <Text style={[estilos.subtitulo, { marginTop: 4 }]}>
                  Por que esta posição (nota {candidato.nota.toFixed(2)})
                </Text>
                {Object.entries(candidato.componentes).map(([chave, valor]) => (
                  <View key={chave} style={estilos.barraLinha}>
                    <Text style={estilos.barraNome}>{NOMES_COMPONENTES[chave] ?? chave}</Text>
                    <View style={estilos.barraFundo}>
                      <View style={[estilos.barra, { width: `${Math.round(valor * 100)}%` }]} />
                    </View>
                  </View>
                ))}
              </>
            )}
          </>
        )}
      </View>

      {candidato && (
        <View style={estilos.bloco}>
          <Text style={estilos.texto}>
            {reais(candidato.preco_estimado)}
            {candidato.preco_estimado !== null ? ` por ${duracao < 60 ? `${duracao} min` : `${duracao / 60} h`}` : ''} ·{' '}
            {candidato.caminhada_min} min a pé ({candidato.caminhada_m} m)
            {candidato.tempo_carro_min !== null ? ` · ${candidato.tempo_carro_min} min de carro` : ''}
          </Text>
          {candidato.motivos.map((m) => (
            <Text key={m} style={estilos.motivo}>✓ {m}</Text>
          ))}
          {candidato.avisos.map((a) => (
            <Text key={a} style={estilos.aviso}>! {a}</Text>
          ))}
        </View>
      )}

      <Text style={estilos.subtitulo}>Ir até a vaga</Text>
      <View style={estilos.linha}>
        <Botao compacto titulo="Waze" onPress={() => navegar('waze')} />
        <Botao compacto titulo="Google Maps" onPress={() => navegar('google')} />
        {Platform.OS === 'ios' && <Botao compacto titulo="Apple Maps" onPress={() => navegar('apple')} />}
      </View>

      {!ehRua && (candidato?.pode_reservar || reservaDestaVaga) && (
        <>
          <Text style={estilos.subtitulo}>Reserva (parceiro)</Text>
          {reservaDestaVaga ? (
            <View style={estilos.bloco}>
              <Text style={estilos.texto}>
                Código <Text style={{ fontWeight: '700' }}>{reservaDestaVaga.codigo}</Text> · válida até{' '}
                {hora(reservaDestaVaga.expira_em)}
              </Text>
              <Text style={estilos.suave}>Mostre o código ou a placa na cancela.</Text>
              <Botao titulo="Cancelar reserva" variante="secundario" carregando={ocupado === 'reserva'} onPress={cancelarReserva} />
            </View>
          ) : (
            <Botao titulo="Reservar por 10 min" carregando={ocupado === 'reserva'} onPress={reservar} />
          )}
        </>
      )}
      {ehRua && <Text style={estilos.suave}>Vagas de rua são espaço público e não podem ser reservadas.</Text>}

      <Text style={estilos.subtitulo}>Estacionar</Text>
      <View style={estilos.bloco}>
        <Text style={estilos.suave}>Por enquanto, nada é cobrado.</Text>
        <TextInput
          value={placa}
          onChangeText={(t) => setPlaca(t.toUpperCase())}
          autoCapitalize="characters"
          placeholder="Placa"
          style={estilos.campo}
        />
        {!perto && <Text style={estilos.aviso}>{avisoDistancia}</Text>}
        <Botao
          titulo={sessaoLocal ? 'Você já tem um estacionamento ativo' : 'Iniciar estacionamento'}
          desabilitado={!!sessaoLocal || !perto}
          carregando={ocupado === 'sessao'}
          onPress={iniciarSessao}
        />
        {!perto && (
          <Botao titulo="Atualizar minha posição" variante="secundario" carregando={ocupado === 'posicao'} onPress={atualizarPosicao} />
        )}
      </View>

      {ehRua && (
        <>
          <Text style={estilos.subtitulo}>Está vendo esta vaga agora?</Text>
          <View style={estilos.linha}>
            <Botao titulo="Está livre" variante="secundario" desabilitado={!perto} carregando={ocupado === 'livre'} onPress={() => reportar(true)} />
            <Botao titulo="Está ocupada" variante="secundario" desabilitado={!perto} carregando={ocupado === 'ocupada'} onPress={() => reportar(false)} />
          </View>
        </>
      )}

      {podeMapear && (
        <>
          <Text style={estilos.subtitulo}>Ajude a mapear</Text>
          <View style={estilos.bloco}>
            <Text style={estilos.suave}>
              {ehRua
                ? 'O que diz a placa deste trecho? Com 2 motoristas concordando, o mapa é atualizado.'
                : 'Informe o preço da placa na entrada ou avise se o estacionamento fechou.'}
            </Text>
            {!perto && <Text style={estilos.aviso}>{avisoDistancia}</Text>}
            {ehRua ? (
              <>
                <Botao titulo="Tem EstaR" variante="secundario" desabilitado={!perto} carregando={ocupado === 'tem_estar'} onPress={() => mapearTrecho('tem_estar')} />
                <Botao titulo="Sem EstaR (estacionamento grátis)" variante="secundario" desabilitado={!perto} carregando={ocupado === 'sem_estar'} onPress={() => mapearTrecho('sem_estar')} />
                <Botao titulo="Proibido estacionar" variante="secundario" desabilitado={!perto} carregando={ocupado === 'proibido'} onPress={() => mapearTrecho('proibido')} />
              </>
            ) : (
              <>
                <View style={estilos.linha}>
                  <TextInput
                    value={preco}
                    onChangeText={setPreco}
                    keyboardType="decimal-pad"
                    placeholder="R$ por hora"
                    style={[estilos.campo, { flex: 1 }]}
                  />
                  <Botao titulo="Informar preço" variante="secundario" desabilitado={!perto} carregando={ocupado === 'preco'} onPress={informarPreco} />
                </View>
                <Botao titulo="Este estacionamento fechou" variante="secundario" desabilitado={!perto} carregando={ocupado === 'fechado'} onPress={informarFechado} />
              </>
            )}
          </View>
        </>
      )}

      <Text style={estilos.subtitulo}>Chegou? Encontrou a vaga?</Text>
      <View style={estilos.linha}>
        <Botao titulo="Sim" variante="secundario" carregando={ocupado === 'sim'} onPress={() => avaliarChegada(true)} />
        <Botao titulo="Não" variante="secundario" carregando={ocupado === 'nao'} onPress={() => avaliarChegada(false)} />
      </View>
    </ScrollView>
  );
}

// "Como estimamos" — transparência sobre a capacidade calculada a partir do mapa.
function TextoEstimativa({ estimativa }: { estimativa: Estimativa }) {
  const descontos = Object.entries(estimativa.descontos_m)
    .map(([nome, m]) => `${nome} (${m} m)`)
    .join(', ');
  const lados = estimativa.lados === 1 ? '1 lado' : `${estimativa.lados} lados`;
  return (
    <Text style={estilos.suave}>
      Como estimamos: quadra de {estimativa.comprimento_m} m, {lados}
      {estimativa.mao_unica ? ' (mão única)' : ''}, 5 m livres em cada esquina
      {descontos ? `, menos ${descontos}` : ''} e {Math.round((1 - estimativa.fator_garagens_nao_mapeadas) * 100)}% a menos
      por garagens que não estão no mapa. Vaga de 5,5 m.
    </Text>
  );
}

const estilos = StyleSheet.create({
  conteudo: { padding: 16, gap: 12, paddingBottom: 40, backgroundColor: cores.fundo },
  vazio: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  titulo: { fontSize: 22, fontWeight: '700', color: cores.marinho },
  subtitulo: { fontSize: 15, fontWeight: '700', color: cores.texto, marginTop: 4 },
  texto: { fontSize: 15, color: cores.texto },
  suave: { fontSize: 13, color: cores.suave },
  selo: { alignSelf: 'flex-start', borderRadius: 14, borderWidth: 1.5, borderColor: cores.marinho, paddingHorizontal: 10, paddingVertical: 4 },
  seloTracejado: { borderStyle: 'dashed' },
  seloTexto: { fontSize: 13, fontWeight: '600', color: cores.marinho },
  estado: { backgroundColor: '#fff', borderRadius: 10, padding: 12, borderLeftWidth: 6, gap: 4 },
  estadoRotulo: { fontSize: 16, fontWeight: '600', color: cores.texto },
  bloco: { backgroundColor: '#fff', borderRadius: 10, padding: 12, gap: 8 },
  link: { fontSize: 14, color: cores.azul, fontWeight: '600' },
  motivo: { fontSize: 14, color: cores.livre },
  aviso: { fontSize: 14, color: cores.talvez },
  linha: { flexDirection: 'row', gap: 10 },
  campo: { borderWidth: 1, borderColor: cores.borda, borderRadius: 10, paddingHorizontal: 12, minHeight: 46, fontSize: 16, color: cores.texto },
  barraLinha: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  barraNome: { width: 120, fontSize: 13, color: cores.suave },
  barraFundo: { flex: 1, height: 8, borderRadius: 4, backgroundColor: cores.borda, overflow: 'hidden' },
  barra: { height: 8, backgroundColor: cores.azul },
});
