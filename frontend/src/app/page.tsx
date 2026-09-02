import VerifyForm from "@/components/VerifyForm";
import HowItWorks from "@/components/HowItWorks";
import RiskMap from "@/components/RiskMap";
import ReportCta from "@/components/ReportCta";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <main>
      <div id="verify">
        <VerifyForm />
      </div>
      <HowItWorks />
      <div id="risk-map">
        <RiskMap />
      </div>
      <ReportCta />
      <Footer />
    </main>
  );
}