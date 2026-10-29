import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

import type { Destino, Reserva, RespostaRecomendacao, Sessao, VagaNoMapa } from './tipos';

interface SessaoLocal {
  sessao: Sessao;
  // Instante (relógio do celular) em que a sessão começou. A contagem regressiva usa
  // a duração da sessão a partir daqui, porque a API pode estar com o relógio simulado.
  inicioLocal: number;
  avisoId: string | null;
}

// Navegação aberta para uma vaga: ao voltar para o app perto dela, perguntamos "Encontrou?".
export interface Navegacao {
  vagaId: string;
  nome: string;
  lat: number;
  lng: number;
  coordenadas: [number, number][] | null;
  desde: number;
}

interface EstadoApp {
  // Raio (m) em que dá para iniciar estacionamento e reportar; vem da API (/saude).
  distanciaMaximaM: number;
  setDistanciaMaximaM: (m: number) => void;
  origem: { lat: number; lng: number; simulada: boolean } | null;
  setOrigem: (o: EstadoApp['origem']) => void;
  destino: Destino | null;
  setDestino: (d: Destino | null) => void;
  vagas: VagaNoMapa[];
  setVagas: (v: VagaNoMapa[]) => void;
  recomendacao: RespostaRecomendacao | null;
  setRecomendacao: (r: RespostaRecomendacao | null) => void;
  reserva: Reserva | null;
  setReserva: (r: Reserva | null) => void;
  sessaoLocal: SessaoLocal | null;
  setSessaoLocal: (s: SessaoLocal | null) => void;
  navegacao: Navegacao | null;
  setNavegacao: (n: Navegacao | null) => void;
  iniciarNavegacao: (n: Omit<Navegacao, 'desde'>) => void;
}

const Contexto = createContext<EstadoApp | null>(null);

export function ProvedorEstado({ children }: { children: ReactNode }) {
  const [distanciaMaximaM, setDistanciaMaximaM] = useState(300);
  const [origem, setOrigem] = useState<EstadoApp['origem']>(null);
  const [destino, setDestino] = useState<Destino | null>(null);
  const [vagas, setVagas] = useState<VagaNoMapa[]>([]);
  const [recomendacao, setRecomendacao] = useState<RespostaRecomendacao | null>(null);
  const [reserva, setReserva] = useState<Reserva | null>(null);
  const [sessaoLocal, setSessaoLocal] = useState<SessaoLocal | null>(null);
  const [navegacao, setNavegacao] = useState<Navegacao | null>(null);
  const iniciarNavegacao = useCallback((n: Omit<Navegacao, 'desde'>) => setNavegacao({ ...n, desde: Date.now() }), []);

  return (
    <Contexto.Provider
      value={{
        distanciaMaximaM, setDistanciaMaximaM, origem, setOrigem, destino, setDestino, vagas, setVagas, recomendacao, setRecomendacao,
        reserva, setReserva, sessaoLocal, setSessaoLocal, navegacao, setNavegacao, iniciarNavegacao,
      }}
    >
      {children}
    </Contexto.Provider>
  );
}

export function useApp(): EstadoApp {
  const valor = useContext(Contexto);
  if (!valor) throw new Error('useApp precisa estar dentro de <ProvedorEstado>');
  return valor;
}

export function duracaoMs(sessao: Sessao): number {
  return new Date(sessao.fim_previsto).getTime() - new Date(sessao.inicio).getTime();
}
