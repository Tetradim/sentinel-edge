declare module '@/lib/utils' {
  export function cn(...inputs: unknown[]): string;
}

declare module 'plotly.js-dist-min' {
  const Plotly: unknown;
  export default Plotly;
}
