import { defineConfig } from "@tarojs/cli"
import path from "path"

export default defineConfig({
  projectName: "brain-rush",
  date: "2026-04-26",
  designWidth: 375,
  deviceRatio: {
    375: 2,
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2
  },
  sourceRoot: "src",
  outputRoot: "dist",
  alias: {
    "@": path.resolve(__dirname, "..", "src")
  },
  plugins: ["@tarojs/plugin-framework-react"],
  framework: "react",
  compiler: "webpack5",
  cache: {
    enable: false
  },
  defineConstants: {
    API_BASE_URL: JSON.stringify(process.env.TARO_APP_API_BASE_URL || "http://127.0.0.1:8000")
  },
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {}
      },
      cssModules: {
        enable: false,
        config: {
          namingPattern: "module",
          generateScopedName: "[name]__[local]___[hash:base64:5]"
        }
      }
    }
  }
})
