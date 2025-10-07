#!/usr/bin/env python3
"""
Demo client for the microservice template analytics capabilities.

This script demonstrates how to use the analytics gRPC endpoints.
"""

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

import grpc
import pandas as pd

# Add the source directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from microservice_template.proto import greeter_pb2, greeter_pb2_grpc


async def main():
    """Demonstrate analytics capabilities."""
    parser = argparse.ArgumentParser(description="Demo the analytics microservice")
    parser.add_argument(
        "--target",
        default="localhost:50051",
        help="The gRPC server target (default: localhost:50051)",
    )
    args = parser.parse_args()

    print("🚀 Microservice Analytics Demo")
    print("=" * 50)
    print(f"🔗 Connecting to: {args.target}")

    # Connect to the service
    async with grpc.aio.insecure_channel(args.target) as channel:
        stub = greeter_pb2_grpc.GreeterServiceStub(channel)

        try:
            # Test basic functionality
            print("\\n1. Testing basic greeting...")
            response = await stub.SayHello(
                greeter_pb2.HelloRequest(name="Analytics Demo")
            )
            print(f"   ✓ {response.message}")

            # Test health check
            print("\\n2. Testing health check...")
            health = await stub.HealthCheck(greeter_pb2.HealthCheckRequest())
            print(f"   ✓ Status: {health.status}, Uptime: {health.uptime}")

            # Generate sample data
            print("\\n3. Generating sample dataset...")
            sample_response = await stub.GenerateSampleData(
                greeter_pb2.SampleDataRequest(n_samples=1000, seed=42)
            )
            print(f"   ✓ {sample_response.message}")

            # Save the sample data for later use
            sample_data_csv = sample_response.data_csv

            # Load data to show structure
            df = pd.read_csv(pd.io.common.StringIO(sample_data_csv))
            print(f"   📊 Dataset shape: {df.shape}")
            print(f"   📊 Columns: {list(df.columns)}")
            print("\\n   Sample data:")
            print(df.head().to_string(index=False))

            # Correlation analysis
            print("\\n4. Performing correlation analysis...")
            corr_response = await stub.AnalyzeCorrelation(
                greeter_pb2.CorrelationRequest(data_csv=sample_data_csv)
            )

            if corr_response.success:
                print(f"   ✓ {corr_response.message}")
                results = json.loads(corr_response.results_json)
                if "strong_correlations" in results:
                    print(
                        f"   📈 Found {len(results['strong_correlations'])} strong correlations"
                    )
                    for corr in results["strong_correlations"][:3]:  # Show first 3
                        print(
                            f"      • {corr['variable_1']} ↔ {corr['variable_2']}: {corr['correlation']:.3f}"
                        )

                # Save correlation plot
                if corr_response.plot_base64:
                    save_plot(corr_response.plot_base64, "correlation_matrix.png")
                    print("   💾 Correlation plot saved as correlation_matrix.png")
            else:
                print(f"   ❌ {corr_response.message}")

            # Clustering analysis
            print("\\n5. Performing clustering analysis...")
            cluster_response = await stub.AnalyzeClustering(
                greeter_pb2.ClusteringRequest(data_csv=sample_data_csv, n_clusters=3)
            )

            if cluster_response.success:
                print(f"   ✓ {cluster_response.message}")
                results = json.loads(cluster_response.results_json)
                print(
                    f"   🎯 Silhouette score: {results.get('silhouette_score', 'N/A'):.3f}"
                )

                # Show cluster summary
                if "cluster_summary" in results:
                    print("   📊 Cluster sizes:")
                    for cluster_id, info in results["cluster_summary"].items():
                        print(
                            f"      • {cluster_id}: {info['size']} samples ({info['percentage']:.1f}%)"
                        )

                # Save clustering plot
                if cluster_response.plot_base64:
                    save_plot(cluster_response.plot_base64, "clustering_analysis.png")
                    print("   💾 Clustering plot saved as clustering_analysis.png")
            else:
                print(f"   ❌ {cluster_response.message}")

            # Distribution analysis
            print("\\n6. Performing distribution analysis...")
            # Use a numeric column from our sample data
            values = df["age"].dropna().tolist()

            dist_response = await stub.AnalyzeDistribution(
                greeter_pb2.DistributionRequest(values=values, column_name="age")
            )

            if dist_response.success:
                print(f"   ✓ {dist_response.message}")
                results = json.loads(dist_response.results_json)

                if "descriptive_stats" in results:
                    stats = results["descriptive_stats"]
                    print(
                        f"   📊 Mean: {stats['mean']:.2f}, Median: {stats['median']:.2f}"
                    )
                    print(f"   📊 Std Dev: {stats['std_dev']:.2f}")
                    print(
                        f"   📊 Skewness: {stats['skewness']:.3f}, Kurtosis: {stats['kurtosis']:.3f}"
                    )

                if "normality_tests" in results:
                    shapiro = results["normality_tests"]["shapiro_wilk"]
                    is_normal = "Yes" if shapiro["is_normal"] else "No"
                    print(
                        f"   🧪 Normal distribution: {is_normal} (p-value: {shapiro['p_value']:.4f})"
                    )

                # Save distribution plot
                if dist_response.plot_base64:
                    save_plot(dist_response.plot_base64, "distribution_analysis.png")
                    print("   💾 Distribution plot saved as distribution_analysis.png")
            else:
                print(f"   ❌ {dist_response.message}")

            print("\\n" + "=" * 50)
            print("🎉 Analytics demo completed successfully!")
            print("\\nGenerated files:")
            print("  • correlation_matrix.png - Correlation heatmap")
            print("  • clustering_analysis.png - K-means clustering visualization")
            print("  • distribution_analysis.png - Distribution analysis plots")

        except grpc.RpcError as e:
            print(f"❌ gRPC Error: {e.code()} - {e.details()}")
            return 1
        except Exception as e:
            print(f"❌ Error: {e}")
            return 1

    return 0


def save_plot(base64_data: str, filename: str) -> None:
    """Save a base64-encoded plot to file."""
    try:
        image_data = base64.b64decode(base64_data)
        with open(filename, "wb") as f:
            f.write(image_data)
    except Exception as e:
        print(f"   ⚠️ Failed to save {filename}: {e}")


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\\n⏹️ Demo interrupted by user")
        sys.exit(130)
