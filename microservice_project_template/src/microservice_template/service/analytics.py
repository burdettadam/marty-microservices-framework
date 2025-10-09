"""Statistical analysis service module."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any, Set

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import structlog
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


@dataclass
class StatisticalSummary:
    """Statistical summary of a dataset."""

    count: int
    mean: float
    median: float
    std_dev: float
    min_value: float
    max_value: float
    quartiles: dict[str, float]
    skewness: float
    kurtosis: float


@dataclass
class AnalyticsResult:
    """Result of analytics operation."""

    success: bool
    message: str
    data: dict[str, Any]
    plot_base64: str | None = None


class AnalyticsService:
    """Service for performing statistical analysis and data visualization."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger(__name__)
        # Set matplotlib to use non-interactive backend for server environments
        plt.switch_backend("Agg")

    def generate_sample_data(
        self, n_samples: int = 1000, seed: int = 42
    ) -> pd.DataFrame:
        """Generate sample dataset for demonstration purposes."""
        np.random.seed(seed)

        data = {
            "age": np.random.normal(35, 10, n_samples).clip(18, 80),
            "income": np.random.lognormal(10, 0.5, n_samples),
            "education_years": np.random.normal(14, 3, n_samples).clip(8, 25),
            "satisfaction_score": np.random.beta(2, 1, n_samples) * 10,
            "category": np.random.choice(
                ["A", "B", "C", "D"], n_samples, p=[0.3, 0.25, 0.25, 0.2]
            ),
        }

        df = pd.DataFrame(data)
        # Add some correlation
        df["spending"] = (
            df["income"] * 0.3
            + df["satisfaction_score"] * 1000
            + np.random.normal(0, 5000, n_samples)
        ).clip(0, None)

        self._logger.info(
            "analytics.sample_data.generated",
            n_samples=n_samples,
            columns=list(df.columns),
        )
        return df

    def descriptive_statistics(
        self, data: list[float], column_name: str = "values"
    ) -> StatisticalSummary:
        """Calculate descriptive statistics for a numeric column."""
        arr = np.array(data)

        if len(arr) == 0:
            raise ValueError("Data array cannot be empty")

        summary = StatisticalSummary(
            count=len(arr),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std_dev=float(np.std(arr)),
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            quartiles={
                "q1": float(np.percentile(arr, 25)),
                "q2": float(np.percentile(arr, 50)),
                "q3": float(np.percentile(arr, 75)),
            },
            skewness=float(stats.skew(arr)),
            kurtosis=float(stats.kurtosis(arr)),
        )

        self._logger.info(
            "analytics.descriptive_stats.calculated",
            column=column_name,
            count=summary.count,
            mean=summary.mean,
        )
        return summary

    def correlation_analysis(self, df: pd.DataFrame) -> AnalyticsResult:
        """Perform correlation analysis and generate correlation matrix heatmap."""
        try:
            # Select only numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) < 2:
                return AnalyticsResult(
                    success=False,
                    message="Need at least 2 numeric columns for correlation analysis",
                    data={},
                )

            # Calculate correlation matrix
            corr_matrix = df[numeric_cols].corr()

            # Create heatmap
            plt.figure(figsize=(10, 8))
            sns.heatmap(
                corr_matrix,
                annot=True,
                cmap="coolwarm",
                center=0,
                square=True,
                linewidths=0.5,
            )
            plt.title("Correlation Matrix")
            plt.tight_layout()

            # Convert plot to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
            buffer.seek(0)
            plot_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()

            self._logger.info(
                "analytics.correlation.completed", n_variables=len(numeric_cols)
            )

            return AnalyticsResult(
                success=True,
                message=f"Correlation analysis completed for {len(numeric_cols)} variables",
                data={
                    "correlation_matrix": corr_matrix.to_dict(),
                    "strong_correlations": self._find_strong_correlations(corr_matrix),
                },
                plot_base64=plot_base64,
            )

        except Exception as e:
            self._logger.error("analytics.correlation.error", error=str(e))
            return AnalyticsResult(
                success=False, message=f"Correlation analysis failed: {e!s}", data={}
            )

    def clustering_analysis(
        self, df: pd.DataFrame, n_clusters: int = 3
    ) -> AnalyticsResult:
        """Perform K-means clustering on numeric data."""
        try:
            # Select numeric columns and handle missing values
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) < 2:
                return AnalyticsResult(
                    success=False,
                    message="Need at least 2 numeric columns for clustering",
                    data={},
                )

            # Prepare data
            data = df[numeric_cols].dropna()
            if len(data) < n_clusters:
                return AnalyticsResult(
                    success=False,
                    message=f"Not enough data points for {n_clusters} clusters",
                    data={},
                )

            # Standardize features
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)

            # Perform clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(scaled_data)

            # Calculate silhouette score
            silhouette_avg = silhouette_score(scaled_data, cluster_labels)

            # Apply PCA for visualization (2D)
            pca = PCA(n_components=2, random_state=42)
            pca_data = pca.fit_transform(scaled_data)

            # Create scatter plot
            plt.figure(figsize=(10, 8))
            scatter = plt.scatter(
                pca_data[:, 0],
                pca_data[:, 1],
                c=cluster_labels,
                cmap="viridis",
                alpha=0.7,
                s=50,
            )
            plt.colorbar(scatter)
            plt.xlabel(
                f"First Principal Component (explains {pca.explained_variance_ratio_[0]:.1%} variance)"
            )
            plt.ylabel(
                f"Second Principal Component (explains {pca.explained_variance_ratio_[1]:.1%} variance)"
            )
            plt.title(f"K-Means Clustering Results (k={n_clusters})")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()

            # Convert plot to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
            buffer.seek(0)
            plot_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()

            # Analyze clusters
            cluster_summary = {}
            data_with_clusters = data.copy()
            data_with_clusters["cluster"] = cluster_labels

            for i in range(n_clusters):
                cluster_data = data_with_clusters[data_with_clusters["cluster"] == i]
                cluster_summary[f"cluster_{i}"] = {
                    "size": len(cluster_data),
                    "percentage": len(cluster_data) / len(data_with_clusters) * 100,
                    "means": cluster_data[numeric_cols].mean().to_dict(),
                }

            self._logger.info(
                "analytics.clustering.completed",
                n_clusters=n_clusters,
                silhouette_score=silhouette_avg,
            )

            return AnalyticsResult(
                success=True,
                message=f"Clustering analysis completed with {n_clusters} clusters",
                data={
                    "n_clusters": n_clusters,
                    "silhouette_score": silhouette_avg,
                    "cluster_summary": cluster_summary,
                    "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
                    "n_samples": len(data),
                },
                plot_base64=plot_base64,
            )

        except Exception as e:
            self._logger.error("analytics.clustering.error", error=str(e))
            return AnalyticsResult(
                success=False, message=f"Clustering analysis failed: {e!s}", data={}
            )

    def distribution_analysis(
        self, data: list[float], column_name: str = "values"
    ) -> AnalyticsResult:
        """Analyze the distribution of a numeric variable."""
        try:
            arr = np.array(data)

            if len(arr) == 0:
                return AnalyticsResult(
                    success=False, message="Data array cannot be empty", data={}
                )

            # Statistical tests
            shapiro_stat, shapiro_p = stats.shapiro(
                arr[:5000]
            )  # Shapiro-Wilk limited to 5000 samples

            # Create distribution plot
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle(f"Distribution Analysis: {column_name}")

            # Histogram
            axes[0, 0].hist(arr, bins=30, alpha=0.7, color="skyblue", edgecolor="black")
            axes[0, 0].set_title("Histogram")
            axes[0, 0].set_xlabel(column_name)
            axes[0, 0].set_ylabel("Frequency")

            # Box plot
            axes[0, 1].boxplot(arr)
            axes[0, 1].set_title("Box Plot")
            axes[0, 1].set_ylabel(column_name)

            # Q-Q plot
            stats.probplot(arr, dist="norm", plot=axes[1, 0])
            axes[1, 0].set_title("Q-Q Plot (Normal Distribution)")

            # Density plot
            axes[1, 1].hist(
                arr,
                bins=30,
                density=True,
                alpha=0.7,
                color="lightgreen",
                edgecolor="black",
            )
            axes[1, 1].set_title("Density Plot")
            axes[1, 1].set_xlabel(column_name)
            axes[1, 1].set_ylabel("Density")

            plt.tight_layout()

            # Convert plot to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
            buffer.seek(0)
            plot_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()

            # Get descriptive statistics
            summary = self.descriptive_statistics(data, column_name)

            self._logger.info(
                "analytics.distribution.completed",
                column=column_name,
                n_samples=len(arr),
            )

            return AnalyticsResult(
                success=True,
                message=f"Distribution analysis completed for {column_name}",
                data={
                    "descriptive_stats": {
                        "count": summary.count,
                        "mean": summary.mean,
                        "median": summary.median,
                        "std_dev": summary.std_dev,
                        "min": summary.min_value,
                        "max": summary.max_value,
                        "quartiles": summary.quartiles,
                        "skewness": summary.skewness,
                        "kurtosis": summary.kurtosis,
                    },
                    "normality_tests": {
                        "shapiro_wilk": {
                            "statistic": float(shapiro_stat),
                            "p_value": float(shapiro_p),
                            "is_normal": float(shapiro_p) > 0.05,
                        }
                    },
                },
                plot_base64=plot_base64,
            )

        except Exception as e:
            self._logger.error("analytics.distribution.error", error=str(e))
            return AnalyticsResult(
                success=False, message=f"Distribution analysis failed: {e!s}", data={}
            )

    def _find_strong_correlations(
        self, corr_matrix: pd.DataFrame, threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Find pairs of variables with strong correlations."""
        strong_corrs = []

        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                corr_value = corr_matrix.iloc[i, j]
                # Handle pandas scalar types
                corr_float = float(corr_value)  # type: ignore[arg-type]
                if abs(corr_float) >= threshold:
                    strong_corrs.append(
                        {
                            "variable_1": corr_matrix.columns[i],
                            "variable_2": corr_matrix.columns[j],
                            "correlation": corr_float,
                            "strength": "strong positive"
                            if corr_float >= threshold
                            else "strong negative",
                        }
                    )

        return strong_corrs
