import Svg, { Circle, Path, Rect } from "react-native-svg";

export default function CategoryIcon({ code, size = 22 }: { code: string; size?: number }) {
  const shapes = (() => {
    switch (code) {
      case "ELECTRONICS": return <><Rect x={5} y={2} width={14} height={20} rx={3} /><Path d="M9 5h6m-5 14h4" /></>;
      case "WALLET": return <><Path d="M4 7V5a2 2 0 0 1 2-2h12v4" /><Rect x={3} y={7} width={18} height={14} rx={3} /><Path d="M21 11h-5a3 3 0 0 0 0 6h5" /><Circle cx={17} cy={14} r={0.6} /></>;
      case "ID_CARD": return <><Rect x={2} y={5} width={20} height={14} rx={3} /><Circle cx={8} cy={10} r={2} /><Path d="M5 16c0-4 6-4 6 0m3-7h5m-5 4h5m-5 3h3" /></>;
      case "BAG": return <><Path d="M8 8V6a4 4 0 0 1 8 0v2" /><Rect x={4} y={8} width={16} height={14} rx={3} /><Path d="M8 8v4m8-4v4" /></>;
      case "CLOTHING": return <Path d="m8 3 4 2 4-2 6 4-3 5-3-2v11H8V10l-3 2-3-5 6-4Z" />;
      case "KEY": return <><Circle cx={8} cy={8} r={5} /><Path d="m11.5 11.5 9 9m-4-4 3-3m-1 5 3-3" /></>;
      case "BOOK_STATIONERY": return <><Rect x={4} y={3} width={16} height={18} rx={2} /><Path d="M8 3v18m3-13h6m-6 4h6" /></>;
      default: return <><Rect x={3} y={3} width={7} height={7} rx={2} /><Rect x={14} y={3} width={7} height={7} rx={2} /><Rect x={3} y={14} width={7} height={7} rx={2} /><Rect x={14} y={14} width={7} height={7} rx={2} /></>;
    }
  })();
  return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#79817C" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">{shapes}</Svg>;
}
