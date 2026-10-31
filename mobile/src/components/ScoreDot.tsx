import { View } from "react-native";
import { bandColor, color } from "../lib/theme";

/** Size grows with the score, color is the score color. Gray "not enough data" is drawn hollow. */
export function ScoreDot({ score, band }: { score: number; band: string }) {
  const size = score ? 3 + score * 1.6 : 4;
  const hollow = !score || band === "thin";
  return (
    <View
      accessible={false}
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: hollow ? "transparent" : bandColor[band],
        borderWidth: hollow ? 1.5 : 0,
        borderColor: score ? bandColor.thin : color.quiet,
      }}
    />
  );
}
