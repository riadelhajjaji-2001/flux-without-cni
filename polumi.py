import pulumi
from pulumi_kubernetes import Provider, helm, yaml
from pulumi_flux import FluxBootstrapGitArgs, FluxBootstrapGit

# Assuming you have already set up your kubeconfig file
provider = Provider("provider", kubeconfig=pulumi.Config().require_secret("./kubeconfig"))

# Using the `pulumi_flux` package to bootstrap the cluster with Flux.
# This will install Flux in the cluster and configure it to synchronize with a specified Git repository.
flux_bootstrap = FluxBootstrapGit("github",
                                  args=FluxBootstrapGitArgs(
                                      path="./clusters/my-cluster",
                                      url="https://github.com/riadelhajjaji-2001/k3s-flux.git",
                                      branch="main",
                                      interval="1m",
                                      namespace="flux-system"
                                  ),
                                  opts=pulumi.ResourceOptions(provider=provider))

# Deploying Cilium as the networking plugin for Kubernetes.
# We use the Helm provider from Pulumi, which allows us to deploy Helm charts easily.
cilium_chart = helm.v3.Chart("cilium",
                             helm.v3.ChartOpts(
                                 chart="cilium",
                                 version="1.15.2",
                                 fetch_opts=helm.v3.FetchOpts(
                                     repo="https://helm.cilium.io/",
                                 )
                             ),
                             opts=pulumi.ResourceOptions(provider=provider))

# Exporting the name of the flux bootstrap deployment as a stack output
pulumi.export('fluxBootstrapName', flux_bootstrap.metadata.apply(lambda m: m.name))
